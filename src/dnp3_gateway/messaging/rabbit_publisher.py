"""LEGACY (DEPRECATED) — RabbitMQ telemetri yayincisi.

Gateway 0.4.x ile telemetri akisi NATS JetStream'e (JetStreamPublisher) tasindi.
Bu modul yalniz su iki amac icin tutulmaktadir:
  1. Rollback senaryosu — gerekirse explicit import edilip eski davranis
     geri yuklenebilir.
  2. Test/debug — RabbitMQ broker davranisini izole olarak test etmek isteyen
     gelistiriciler.

YENI KOD KULLANMAYIN. `messaging/__init__.py` bu sinifi varsayilan import
etmez; ihtiyac duyan `from dnp3_gateway.messaging.rabbit_publisher import
RabbitPublisher` ile explicit import edebilir.

Asagidaki implementasyon dual-publish doneminden kalmadir (mandatory=True +
heartbeat/socket_timeout/blocked_connection_timeout); cutover sonrasi
production'da artik cagrilmiyor.

----
Publisher-confirm destekli, thread-safe, yeniden-baglanan RabbitMQ yayinci.

Gateway tek baglanti + tek channel uzerinden mesaj yayinlar. Baglanti dustugunde
bir sonraki `publish()` cagrisinda otomatik yeniden kurulur. Ayni publisher birden
fazla thread'den cagrilirsa dahili lock ile korunur.

Exchange `hsl.events` (topic, durable) olarak declare edilir; tag-engine ayni
exchange'de binding yapar. Mesajlar `delivery_mode=2` (persistent) + publisher
confirms + mandatory=True modunda gonderilir:
  * delivery_mode=2: broker disk'e yazana kadar ack vermez (persistent).
  * confirm_delivery: broker mesaji kabul etti mi (`basic.ack`) yoksa
    reddetti mi (`basic.nack`) anlasilir.
  * mandatory=True: mesaj hicbir queue'ya route edilemezse broker `basic.return`
    gonderir, pika `UnroutableError` raise eder. Boylece exchange/binding
    yanlislari sessizce veri kaybi olarak gizlenmez.

Hata tipleri:
  * UnroutableError / NackError → MESAJ-SPESIFIK hata: kanali kapatma, outbox'a
    yaz (caller yapacak). Channel kapatilirsa sonraki publish'lerin maliyeti
    artar (yeniden declare).
  * ConnectionClosed / ChannelClosed / StreamLostError / OSError →
    KANAL/BAGLANTI hatasi: connection sifirla. Bir sonraki publish yeniden
    baglanir.

Connection parametreleri:
  * heartbeat=30sn: broker idle drop'unu bekletmeden tespit eder.
  * blocked_connection_timeout=10sn: broker memory/disk alarm verdiginde
    sonsuza kadar bekleme.
  * socket_timeout=10sn: TCP read/write zaman asimi (Windows + NAT idle
    drop'larinda dakikalarca takilmayi onler).
  Parametreler URL'de yoksa ConnectionParameters seviyesinde override edilir.
"""

from __future__ import annotations

import json
import logging
import threading
from typing import Any

import pika
from pika.exceptions import (
    AMQPConnectionError,
    AMQPError,
    ChannelClosed,
    ConnectionClosed,
    NackError,
    StreamLostError,
    UnroutableError,
)

logger = logging.getLogger(__name__)


# Mesaj-spesifik hatalar: channel ve connection saglikli, sadece BU mesaj
# kabul edilmedi. Channel'i acik tutariz; caller outbox'a yazar.
_MESSAGE_LEVEL_ERRORS: tuple[type[BaseException], ...] = (NackError, UnroutableError)

# Channel/connection seviyesi hatalar: kanali sifirla, bir sonraki publish
# yeniden baglansin.
_CONNECTION_LEVEL_ERRORS: tuple[type[BaseException], ...] = (
    AMQPConnectionError,
    ConnectionClosed,
    ChannelClosed,
    StreamLostError,
    OSError,
)


class RabbitPublisher:
    def __init__(
        self,
        *,
        url: str,
        exchange: str,
        routing_key: str,
        heartbeat_sec: int = 30,
        blocked_connection_timeout_sec: int = 10,
        socket_timeout_sec: float = 10.0,
    ) -> None:
        self.url = url
        self.exchange = exchange
        self.routing_key = routing_key
        self._heartbeat_sec = heartbeat_sec
        self._blocked_connection_timeout_sec = blocked_connection_timeout_sec
        self._socket_timeout_sec = socket_timeout_sec
        self._connection: pika.BlockingConnection | None = None
        self._channel: Any = None
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ API ---
    def publish(
        self,
        payload: dict[str, Any],
        *,
        message_id: str,
        correlation_id: str | None = None,
        headers: dict[str, Any] | None = None,
    ) -> None:
        """Tek bir telemetri event'ini exchange'e yayinlar.

        Hata tipleri:
          * NackError / UnroutableError -> MESAJ-spesifik; kanal saglikli kalir,
            caller outbox'a yazar (raise edilir).
          * AMQP connection/channel/OS hatasi -> kanal+baglanti reset edilir,
            sonraki publish yeniden kurar.
        """
        with self._lock:
            try:
                channel = self._ensure_channel()
                channel.basic_publish(
                    exchange=self.exchange,
                    routing_key=self.routing_key,
                    body=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                    properties=pika.BasicProperties(
                        content_type="application/json",
                        delivery_mode=2,
                        message_id=message_id,
                        correlation_id=correlation_id or message_id,
                        headers=headers or None,
                    ),
                    mandatory=True,
                )
            except _MESSAGE_LEVEL_ERRORS as exc:
                # Mesaj-spesifik: routing-key yanlis, queue yok, broker nack
                # etti. Kanal hala saglikli — kapatmiyoruz; caller outbox'a yazar.
                logger.warning(
                    "rabbit_publish_message_rejected message_id=%s error_type=%s error=%s",
                    message_id,
                    type(exc).__name__,
                    exc,
                )
                raise
            except _CONNECTION_LEVEL_ERRORS:
                # Baglanti veya kanal hatasi: tum durumu sifirla.
                self._force_close()
                raise
            except AMQPError:
                # Bilinmeyen AMQP hatasi: defansif olarak reset.
                self._force_close()
                raise

    def close(self) -> None:
        with self._lock:
            self._force_close()

    # ---------------------------------------------------------- internal ---
    def _connection_params(self) -> pika.ConnectionParameters:
        """URL parametrelerini al, sonra heartbeat/timeout override'larini uygula.

        URLParameters'tan baslayip ConnectionParameters degerlerini bireysel
        olarak set ediyoruz; boylece URL'de zaten heartbeat varsa onun
        uzerine yazmiyoruz (kullanici bilinçli set ettiyse). URL'de YOKSA
        constructor default'lari devreye girer.
        """
        params = pika.URLParameters(self.url)
        # pika.URLParameters default heartbeat=None ('broker negotiates' demek).
        # Bunu kullanici explicit set etmediyse override etmek istiyoruz.
        # URL'de "heartbeat=" yoksa pika None birakir; biz de override edebiliriz.
        if "heartbeat=" not in self.url:
            params.heartbeat = self._heartbeat_sec
        if "blocked_connection_timeout=" not in self.url:
            params.blocked_connection_timeout = self._blocked_connection_timeout_sec
        if "socket_timeout=" not in self.url:
            params.socket_timeout = self._socket_timeout_sec
        return params

    def _ensure_channel(self) -> Any:
        if self._connection is None or self._connection.is_closed:
            self._connection = pika.BlockingConnection(self._connection_params())
            self._channel = None
        if self._channel is None or self._channel.is_closed:
            channel = self._connection.channel()
            channel.exchange_declare(
                exchange=self.exchange, exchange_type="topic", durable=True
            )
            channel.confirm_delivery()
            self._channel = channel
            logger.debug(
                "rabbit_publisher_channel_opened exchange=%s heartbeat=%ss socket_timeout=%ss",
                self.exchange,
                self._heartbeat_sec,
                self._socket_timeout_sec,
            )
        return self._channel

    def _force_close(self) -> None:
        try:
            if self._channel is not None and not self._channel.is_closed:
                self._channel.close()
        except Exception:  # noqa: BLE001
            logger.debug("rabbit_publisher_channel_close_error", exc_info=True)
        try:
            if self._connection is not None and not self._connection.is_closed:
                self._connection.close()
        except Exception:  # noqa: BLE001
            logger.debug("rabbit_publisher_connection_close_error", exc_info=True)
        self._channel = None
        self._connection = None
