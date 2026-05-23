from pydantic_settings import BaseSettings
import os

env = os.getenv("APP_ENV", "dev")

class Settings(BaseSettings):
    APP_ENV: str = env
    DASHSCOPE_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""

    class Config:
        env_file = f".env.{env}"  # dev/staging/prod

settings = Settings()