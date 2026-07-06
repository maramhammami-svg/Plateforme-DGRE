from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg2://dgre:dgre_pass@db:5432/dgre_poc"
    jwt_secret: str = "change-me-in-prod"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 120
    enable_docs: bool = False

    class Config:
        env_file = ".env"


settings = Settings()
