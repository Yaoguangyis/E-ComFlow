from pydantic_settings import BaseSettings


class Settings(BaseSettings):

    APP_ENV: str = "dev"

    DASHSCOPE_API_KEY: str = ""

    OPENAI_API_KEY: str = ""

    ANTHROPIC_API_KEY: str = ""

    class Config:

        env_file = ".env"


settings = Settings()