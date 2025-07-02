import os
from dataclasses import dataclass
from dotenv import load_dotenv

@dataclass
class Config:
    vault_url: str
    vault_token: str
    vault_secret_path: str
    postgres_dsn: str
    web3_provider_url: str
    # Logging and Monitoring
    log_level: str
    environment: str
    app_version: str
    enable_metrics: bool


def load_config() -> Config:
    load_dotenv()
    return Config(
        vault_url=os.getenv('VAULT_URL', 'http://127.0.0.1:8200'),
        vault_token=os.getenv('VAULT_TOKEN', ''),
        vault_secret_path=os.getenv('VAULT_SECRET_PATH', 'eth_wallets'),
        postgres_dsn=os.getenv('POSTGRES_DSN', 'postgresql://user:password@localhost:5432/dbname'),
        web3_provider_url=os.getenv('WEB3_PROVIDER_URL', 'http://localhost:8545'),
        # Logging and Monitoring
        log_level=os.getenv('LOG_LEVEL', 'INFO'),
        environment=os.getenv('ENVIRONMENT', 'development'),
        app_version=os.getenv('APP_VERSION', '1.0.0'),
        enable_metrics=os.getenv('ENABLE_METRICS', 'true').lower() == 'true',
    ) 