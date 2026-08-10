from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    llm_provider: str = "anthropic"  # "anthropic" | "google"

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-5"

    google_api_key: str = ""
    google_model: str = "gemini-2.5-pro"

    database_url: str = "sqlite:///./suits_ai.db"

    class Config:
        env_file = ".env"


settings = Settings()
