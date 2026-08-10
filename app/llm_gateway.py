"""LLM gateway: one call site that resolves to Anthropic or Google Gemini.

Lets the caller (or the request payload) pick the active provider/model
instead of hardcoding a single vendor throughout the agent code.
"""
from functools import lru_cache

from langchain_core.language_models.chat_models import BaseChatModel

from app.config import settings

SUPPORTED_PROVIDERS = ("anthropic", "google")


@lru_cache(maxsize=8)
def _build_model(provider: str, model: str | None) -> BaseChatModel:
    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=model or settings.anthropic_model,
            api_key=settings.anthropic_api_key,
        )
    if provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=model or settings.google_model,
            google_api_key=settings.google_api_key,
        )
    raise ValueError(f"Unknown LLM provider '{provider}'. Choose from {SUPPORTED_PROVIDERS}.")


def get_llm(provider: str | None = None, model: str | None = None) -> BaseChatModel:
    """Return a chat model for the requested provider, defaulting to settings.llm_provider.

    Every agent should call this instead of instantiating a provider SDK directly,
    so swapping the active model is a config/request change, not a code change.
    """
    resolved_provider = (provider or settings.llm_provider).lower()
    return _build_model(resolved_provider, model)
