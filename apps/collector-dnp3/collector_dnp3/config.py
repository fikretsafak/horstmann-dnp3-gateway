from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Gateway kimligi - her collector instance icin benzersiz olmali
    gateway_code: str = "GW-001"
    gateway_token: str = "gw-default-token"

    # Gateway calisma modu: mock | dnp3
    gateway_mode: str = "mock"

    # Health server
    worker_health_host: str = "127.0.0.1"
    worker_health_port: int = 8020

    # Backend API - konfigurasyon ve cihaz listesi buradan cekilir
    backend_api_url: str = "http://127.0.0.1:8000/api/v1"
    config_refresh_sec: int = 30
    config_timeout_sec: int = 5

    # RabbitMQ - tag-engine'e raw telemetry gonderilir
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"
    rabbitmq_exchange: str = "hsl.events"
    rabbitmq_routing_key: str = "telemetry.raw_received"

    # Mock mod icin sinyal profilleri (signal_profile -> signal key listesi)
    signal_keys_csv: str = "voltage,current,power"

    # Backend hic cihaz donmezse polling dongusunun beklemesi icin varsayilan interval
    default_poll_interval_sec: int = 5

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def default_signal_keys(self) -> list[str]:
        return [item.strip() for item in self.signal_keys_csv.split(",") if item.strip()]


settings = Settings()
