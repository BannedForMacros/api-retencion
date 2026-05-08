from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ─── SQL Server ──────────────────────────────────────────────────────────
    db_server: str = "localhost"
    db_port: int = 1433
    db_database: str = "db_fsm_emmel"
    db_driver: str = "ODBC Driver 18 for SQL Server"

    # Trusted_Connection (Windows Auth). Si es True, db_user/db_password se ignoran.
    db_trusted_connection: bool = True

    # SQL Auth (solo si db_trusted_connection = False)
    db_user: str = ""
    db_password: str = ""

    # TLS
    db_encrypt: str = "yes"
    db_trust_server_certificate: str = "yes"

    # Timeouts (segundos)
    db_login_timeout: int = 10
    db_query_timeout: int = 60

    # ─── API ─────────────────────────────────────────────────────────────────
    api_title: str = "Retenciones Datamarket API"
    api_version: str = "0.1.0"

    # CORS: lista separada por comas en el .env, ej. "http://localhost:3000,http://localhost:8000"
    cors_origins: str = "*"


settings = Settings()


def build_connection_string() -> str:
    """Construye la cadena ODBC en función de los settings."""
    server = settings.db_server
    if settings.db_port and settings.db_port != 1433:
        server = f"{server},{settings.db_port}"

    parts = [
        f"Driver={{{settings.db_driver}}}",
        f"Server={server}",
        f"Database={settings.db_database}",
        f"Encrypt={settings.db_encrypt}",
        f"TrustServerCertificate={settings.db_trust_server_certificate}",
    ]

    if settings.db_trusted_connection:
        parts.append("Trusted_Connection=Yes")
    else:
        parts.append(f"UID={settings.db_user}")
        parts.append(f"PWD={settings.db_password}")

    return ";".join(parts) + ";"


def parse_cors_origins() -> list[str]:
    raw = settings.cors_origins.strip()
    if raw == "*":
        return ["*"]
    return [o.strip() for o in raw.split(",") if o.strip()]
