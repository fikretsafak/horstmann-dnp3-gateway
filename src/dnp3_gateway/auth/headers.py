"""Backend HTTP cagrilarina eklenecek guvenli baslik ureticileri."""

from __future__ import annotations

from uuid import uuid4

from dnp3_gateway.auth.identity import GatewayIdentity


def build_config_request_headers(identity: GatewayIdentity) -> dict[str, str]:
    """Config cekme (GET) istegi icin baslik sozlugu.

    Ileride: ayni fonksiyon uzerine HMAC, OAuth2 client assertion veya
    mTLS sertifika seri numarasi (custom header) eklenebilir; consumer
    (BackendConfigClient) tek cagrida toplu header birlestirmesi yapar.
    """

    correlation = str(uuid4())
    h: dict[str, str] = {
        "X-Gateway-Token": identity.token,
        # Path ile ayni olmali; backend path/header uyumsuzlugunda 400 doner (defans derinligi).
        "X-Gateway-Code": identity.gateway_code,
        "X-Gateway-Instance-Id": identity.instance_id,
        "X-Request-Id": correlation,
        "User-Agent": f"Horstmann-Dnp3Gateway/{identity.app_version} (env={identity.app_environment})",
    }
    h["X-Gateway-Client"] = f"dnp3-gateway/{identity.app_version}"
    return h
