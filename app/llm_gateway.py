"""LLM gateway: one call site that resolves to Anthropic or Google Gemini.

Lets the caller (or the request payload) pick the active provider/model
instead of hardcoding a single vendor throughout the agent code.
"""
from functools import lru_cache
from typing import Any, TypeVar

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.runnables import Runnable
from pydantic import BaseModel

from app.config import settings

T = TypeVar("T", bound=BaseModel)

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


def invoke_structured(
    prompt: Runnable, llm: BaseChatModel, schema: type[T], inputs: dict[str, Any]
) -> tuple[T, dict[str, int | None]]:
    """Runs prompt | llm with structured output, returning (parsed_result, token_usage).

    Uses include_raw=True so the underlying AIMessage (and its provider-reported
    usage_metadata) is still reachable - with_structured_output alone throws that
    away, which is where token counts for the usage dashboard would otherwise
    silently disappear.
    """
    structured_llm = llm.with_structured_output(schema, include_raw=True)
    chain = prompt | structured_llm
    response = chain.invoke(inputs)
    parsed = response["parsed"]
    raw = response["raw"]
    usage = getattr(raw, "usage_metadata", None) or {}

    if parsed is None:
        # include_raw=True changes the failure mode from "raises" to "returns
        # parsed: None" - surface it as a clear error instead of letting a
        # None ripple into the caller and fail confusingly downstream.
        raise ValueError(
            f"Model returned output that didn't match the {schema.__name__} schema: "
            f"{response.get('parsing_error')!r}"
        )

    return parsed, {
        "input_tokens": usage.get("input_tokens"),
        "output_tokens": usage.get("output_tokens"),
    }
