"""Gateway ana giris noktasi.

Calisma akisi:
    1. Loglama + health HTTP sunucusu acilir.
    2. Arkaplan thread'i backend API'den `CONFIG_REFRESH_SEC` araliklarla
       konfigurasyon ceker ve `GatewayState`'i gunceller.
    3. Ana thread `default_poll_interval_sec` araliginda uyanip okunma vakti
       gelen cihazlari `poller.run_poll_cycle` ile okur/yayinlar.
    4. SIGINT/SIGTERM alindiginda graceful shutdown:
         - config refresh thread durdurulur
         - poller kapanir
         - DNP3 session'lari + RabbitMQ kanali kapatilir
         - health HTTP sunucusu kapatilir
"""

from __future__ import annotations

import logging
import signal
import time
from threading import Event, Thread

from dnp3_gateway import __version__
from dnp3_gateway.adapters import TelemetryReader, build_adapter
from dnp3_gateway.auth import GatewayIdentity, bootstrap_gateway_identity
from dnp3_gateway.backend import BackendConfigClient, GatewayConfigError
from dnp3_gateway.config import Settings, settings
from dnp3_gateway.health_server import GatewayMetrics, start_health_server
from dnp3_gateway.logging_setup import configure_logging
from dnp3_gateway.messaging import Outbox, OutboxRetrier, RabbitPublisher
from dnp3_gateway.messaging.resilient_publisher import ResilientPublisher
from dnp3_gateway.poller import run_poll_cycle
from dnp3_gateway.state import GatewayState

logger = logging.getLogger("dnp3_gateway")


def _print_console_banner(
    *,
    cfg: Settings,
    identity: GatewayIdentity,
    actual_health_port: int,
) -> None:
    """Konsolda port / URL / coklu instance kurallarini net gosterir."""

    host = cfg.worker_health_host
    port = actual_health_port
    health_url = f"http://{host}:{port}/health"
    config_path = f"{cfg.backend_api_url.rstrip('/')}/gateways/{identity.gateway_code}/config"
    print("", flush=True)
    print("  --- Horstmann DNP3 Gateway ---", flush=True)
    print(f"  Surum ............ {__version__}", flush=True)
    print(f"  GATEWAY_CODE ..... {identity.gateway_code}", flush=True)
    print(f"  Instance id ...... {identity.instance_id}", flush=True)
    print(f"  Saglik (HTTP) .... {health_url}   <- bu portta dinler (WORKER_HEALTH_PORT)", flush=True)
    print(
        f"  DNP3 (cihaz) ...... varsayilan TCP {cfg.dnp3_tcp_port} (.env DNP3_TCP_PORT); "
        "IP/port/DNP3 adresi asil kaynak: backend config `devices[]`",
        flush=True,
    )
    print(f"  Backend config ... GET {config_path}", flush=True)
    print(
        "  Token ............ .env icinde GATEWAY_TOKEN; backend `gateways.token` ile AYNI olmali.",
        flush=True,
    )
    print(
        "  Coklu proses ..... Ayni GATEWAY_CODE+token ile iki kopya ACMAYIN. "
        "Ikinci sunucu/servis -> yeni kod (orn. GW-002), arayuzden yeni gateway + yeni token + ayri .env.",
        flush=True,
    )
    if cfg.is_mock_mode:
        print(
            "  *** UYARI: GATEWAY_MODE=mock  ->  SAHADAN DNP3 ILE OKUMA YOK; "
            "degerler ureticidir. Gercek cihaz icin .env: GATEWAY_MODE=dnp3 (+ pip install nfm-dnp3).",
            flush=True,
        )
    print("  ------------------------------", flush=True)
    print("", flush=True)


def _mask_secret(value: str, *, keep: int = 4) -> str:
    v = value.strip()
    if len(v) <= 2 * keep:
        return "***"
    return f"{v[:keep]}...{v[-keep:]}"


def _run_config_refresh(
    *,
    client: BackendConfigClient,
    state: GatewayState,
    config_ready: Event,
    stop_event: Event,
    refresh_sec: int,
) -> None:
    last_active_state: bool | None = None
    while not stop_event.is_set():
        try:
            config = client.fetch_config()
            changed = state.update(config)
            config_ready.set()
            if changed:
                logger.info(
                    "config_refresh gateway=%s version=%s devices=%s signals=%s active=%s",
                    config.gateway_code,
                    config.config_version,
                    len(config.devices),
                    len(config.signals),
                    config.is_active,
                )
            if last_active_state is None or last_active_state != config.is_active:
                last_active_state = config.is_active
                if config.is_active:
                    logger.info("gateway_polling_resumed gateway=%s", config.gateway_code)
                else:
                    logger.warning(
                        "gateway_polling_suspended gateway=%s (is_active=False)",
                        config.gateway_code,
                    )
        except GatewayConfigError as exc:
            err = str(exc)
            logger.error("config_refresh_error gateway=%s error=%s", client.gateway_code, exc)
            if "404" in err:
                logger.error(
                    "config_404_cozum: Backendde '%s' kodlu gateway yok. "
                    "Arayüz: Mühendislik → Gateway Yönetimi → ayni Kod + ayni Token ile kayit acin. "
                    "Veya .env GATEWAY_CODE yanlis.",
                    client.gateway_code,
                )
            elif "401" in err:
                logger.error(
                    "config_401_cozum: GATEWAY_TOKEN, backend gateways.token ile eslesmiyor; .env guncelleyin.",
                )
        stop_event.wait(timeout=max(5, refresh_sec))


def _install_signal_handlers(stop_event: Event) -> None:
    def _handler(signum, _frame):  # type: ignore[no-untyped-def]
        logger.info("signal_received signum=%s shutdown=starting", signum)
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, _handler)
        except (ValueError, OSError):
            # Windows alt thread'lerde bazi sinyaller atanamaz; gecici gec
            pass


def _tls_verify_param(cfg: Settings) -> bool | str:
    """requests `verify` argumani: True | False | CA bundle yolu."""

    if cfg.backend_api_ca_path and str(cfg.backend_api_ca_path).strip():
        return str(cfg.backend_api_ca_path).strip()
    return cfg.backend_api_verify_ssl


def run(current_settings: Settings | None = None) -> int:
    cfg = current_settings or settings
    configure_logging(level=cfg.log_level, fmt=cfg.log_format)

    identity = bootstrap_gateway_identity(settings=cfg, app_version=__version__)
    # Konsola (stdout): log seviyesinden bagimsiz; kurulumda token eslemesini dogrulamak icin.
    if cfg.show_gateway_token_on_start:
        print(f"[dnp3-gateway] GATEWAY_TOKEN={identity.token}", flush=True)
    else:
        print(
            f"[dnp3-gateway] GATEWAY_TOKEN (maskeli)={_mask_secret(identity.token)}  "
            f"(tam metin icin .env: SHOW_GATEWAY_TOKEN_ON_START=true)",
            flush=True,
        )
    logger.info(
        "dnp3_gateway_starting version=%s gateway=%s instance=%s env=%s mode=%s backend=%s",
        __version__,
        identity.gateway_code,
        identity.instance_id,
        identity.app_environment,
        cfg.gateway_mode,
        cfg.backend_api_url,
    )

    state = GatewayState()
    config_ready = Event()
    stop_event = Event()

    health, metrics, actual_health_port = start_health_server(
        host=cfg.worker_health_host,
        port=cfg.worker_health_port,
        state=state,
        gateway_code=identity.gateway_code,
        gateway_mode=cfg.gateway_mode,
        config_ready=config_ready,
        instance_id=identity.instance_id,
        app_environment=identity.app_environment,
    )
    # Banner: gercek (auto-assigned olabilir) health portunu yansitabilmek icin
    # health_server start sonrasi yazdirilir.
    _print_console_banner(cfg=cfg, identity=identity, actual_health_port=actual_health_port)

    broker = RabbitPublisher(
        url=cfg.rabbitmq_url,
        exchange=cfg.rabbitmq_exchange,
        routing_key=cfg.rabbitmq_routing_key,
    )
    # Outbox: RabbitMQ erisilemezse mesajlari diske yaz, retrier sonra gonderir.
    # Process restart'a dayanikli (kalici SQLite); at-least-once delivery.
    from pathlib import Path

    outbox_path = Path(cfg.gateway_state_dir) / f"outbox_{identity.gateway_code}.db"
    outbox = Outbox(outbox_path)
    pending = outbox.pending_count()
    if pending:
        logger.warning(
            "outbox_pending_messages count=%s db=%s — retrier hizla bosaltacak",
            pending,
            outbox_path,
        )
    publisher = ResilientPublisher(broker=broker, outbox=outbox)
    retrier = OutboxRetrier(
        outbox,
        publish_fn=publisher.publish_outbox_row,
        poll_interval_sec=2.0,
        batch_size=200,
    )
    retrier.start()

    reader: TelemetryReader = build_adapter(cfg)
    logger.info("telemetry_adapter=%s", type(reader).__name__)
    if cfg.is_mock_mode:
        logger.warning(
            "TELEMETRI_KAYNAGI=MOCK — sahadan DNP3 okunmuyor; uretici degerler. "
            "Cati (RabbitMQ) akisi calisir ama kaynak cihaz degil. Gercek okuma: "
            "GATEWAY_MODE=dnp3, nfm-dnp3 (dnp3py), cihaz IP/port/DNP3 adresi backend config."
        )
    else:
        logger.info(
            "TELEMETRI_KAYNAGI=DNP3 — library=%s; baglanti: backend devices[] "
            "(ip, dnp3_address, istege bagli dnp3_tcp_port; yoksa varsayilan port=%s).",
            (cfg.dnp3_library or "yadnp3"),
            cfg.dnp3_tcp_port,
        )

    config_client = BackendConfigClient(
        base_url=cfg.backend_api_url,
        identity=identity,
        timeout_sec=cfg.config_timeout_sec,
        verify=_tls_verify_param(cfg),
    )

    refresh_thread = Thread(
        target=_run_config_refresh,
        kwargs={
            "client": config_client,
            "state": state,
            "config_ready": config_ready,
            "stop_event": stop_event,
            "refresh_sec": cfg.config_refresh_sec,
        },
        name="config-refresh",
        daemon=True,
    )
    refresh_thread.start()

    _install_signal_handlers(stop_event)

    # Ilk config gelene kadar 15 saniye bekle. Backend erisilemezse yine de
    # dongu calismaya baslar ama `is_active` False oldugu icin mesaj yayinlamaz.
    if not config_ready.wait(timeout=15):
        logger.warning("first_config_not_received_yet gateway=%s", identity.gateway_code)

    logger.info(
        "dnp3_gateway_running health=%s:%s instance=%s",
        cfg.worker_health_host,
        actual_health_port,
        identity.instance_id,
    )

    try:
        while not stop_event.is_set():
            now_monotonic = time.monotonic()
            due_count = len(state.due_devices(now_monotonic))
            published = run_poll_cycle(
                gateway_code=identity.gateway_code,
                state=state,
                reader=reader,
                publisher=publisher,
                now_monotonic=now_monotonic,
                max_parallel=cfg.max_parallel_devices,
            )
            if due_count or published:
                metrics.record_cycle(devices=due_count, published=published)
            if published:
                logger.info(
                    "poll_cycle gateway=%s published=%s devices=%s version=%s",
                    identity.gateway_code,
                    published,
                    due_count,
                    state.config_version(),
                )
            stop_event.wait(timeout=max(1, cfg.default_poll_interval_sec))
    except KeyboardInterrupt:
        logger.info("dnp3_gateway_interrupted")
    finally:
        logger.info("dnp3_gateway_shutdown_starting")
        stop_event.set()
        try:
            reader.close()
        except Exception:  # noqa: BLE001
            logger.debug("reader_close_error", exc_info=True)
        try:
            retrier.stop()
        except Exception:  # noqa: BLE001
            logger.debug("retrier_stop_error", exc_info=True)
        publisher.close()
        try:
            health.shutdown()
            health.server_close()
        except Exception:  # noqa: BLE001
            logger.debug("health_server_shutdown_error", exc_info=True)
        pending = outbox.pending_count()
        if pending:
            logger.warning(
                "shutdown_pending_outbox count=%s db=%s — sonraki baslangicta gonderilecek",
                pending,
                outbox_path,
            )
        logger.info("dnp3_gateway_stopped")
    return 0


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
