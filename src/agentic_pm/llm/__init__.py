import os

from agentic_pm.config.team import LLMSettings
from agentic_pm.llm.base import ChatMessage, Completion, LLMError, LLMProvider
from agentic_pm.llm.openai_compatible import OpenAICompatibleProvider


def provider_from_settings(settings: LLMSettings) -> LLMProvider:
    """Build the configured provider. Hosted providers will register here as optional extras."""
    if settings.provider == "openai-compatible":
        return OpenAICompatibleProvider(
            model=settings.model,
            base_url=settings.base_url,
            reasoning_effort=settings.reasoning_effort,
            # Only needed for secured servers; never stored in team.yaml.
            api_key=os.environ.get("AGENT_PM_LLM_API_KEY"),
        )
    raise ValueError(f"unknown LLM provider '{settings.provider}'")


__all__ = [
    "ChatMessage",
    "Completion",
    "LLMError",
    "LLMProvider",
    "OpenAICompatibleProvider",
    "provider_from_settings",
]
