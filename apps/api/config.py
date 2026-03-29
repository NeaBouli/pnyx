from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://ekklesia:devpassword@localhost/ekklesia"
    redis_url: str = "redis://localhost:6379"
    server_salt: str = "dev-salt-change-in-production"
    anthropic_api_key: str = ""
    truerepublic_enabled: bool = False
    env: str = "development"

    class Config:
        env_file = ".env"

settings = Settings()
