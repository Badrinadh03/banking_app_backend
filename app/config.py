from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440
    jwt_remember_device_expire_minutes: int = 43200
    cors_origins: str = "http://localhost:5173"

    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    smtp_use_tls: bool = True

    # Fernet key (urlsafe base64, 32 bytes) for encrypting debit card
    # numbers/CVVs at rest. Falls back to a key derived from jwt_secret_key
    # if unset — production deployments should set this explicitly.
    card_encryption_key: str = ""

    # Anthropic API key powering the in-app virtual assistant. Unset by
    # default — the assistant endpoints return a clear "not configured"
    # error rather than the app failing to boot.
    anthropic_api_key: str = ""

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    @property
    def email_sending_enabled(self) -> bool:
        return bool(self.smtp_username and self.smtp_password)

    @property
    def assistant_enabled(self) -> bool:
        return bool(self.anthropic_api_key)

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
