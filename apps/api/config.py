from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    database_url: str = "postgresql+asyncpg://ekklesia:devpassword@localhost/ekklesia"
    redis_url: str = "redis://localhost:6379"
    server_salt: str = "dev-salt-change-in-production"
    anthropic_api_key: str = ""
    truerepublic_enabled: bool = False
    arweave_wallet_path: str = ""  # MOD-08: Pfad zur Arweave Wallet JSON
    env: str = "development"

settings = Settings()
