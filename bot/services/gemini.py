"""
Gemini API Compatibility Layer

This module provides backward compatibility for existing code that uses the old
gemini.py interface. It delegates all calls to the new LLM provider system,
which supports both Gemini and OpenAI based on the LLM_PROVIDER environment variable.

All existing calling code (start.py, settings.py, content_filter.py, etc.) works
without modification.

Supports:
- Automatic provider selection based on LLM_PROVIDER environment variable
- Gemini-specific features (thinking mode, Google Search) when using Gemini provider
- Seamless fallback when using OpenAI provider

Note: OpenAI provider does not support native web search. If you call
call_gemini_with_search() with LLM_PROVIDER=openai, it will raise NotImplementedError.
"""
import logging
from typing import Optional, Tuple

from .llm_factory import LLMFactory, call_llm_text, call_llm_json

logger = logging.getLogger(__name__)


def _get_provider():
    """Get the global LLM provider instance (Gemini or OpenAI based on config)."""
    return LLMFactory.get_provider()


async def call_gemini(
    prompt: str,
    system_instruction: Optional[str] = None,
    temperature: float = 1.0,
    context: str = "call_gemini",
) -> str:
    """
    Generate content using the full LLM provider chain with automatic fallback.
    """
    result, used = await call_llm_text(
        prompt=prompt,
        system_instruction=system_instruction or "",
        temperature=temperature,
        context=context,
    )
    if result is None:
        raise RuntimeError(f"All LLM providers failed (context={context})")
    return result


async def call_gemini_json(
    prompt: str,
    system_instruction: Optional[str] = None,
    temperature: float = 1.0,
    context: str = "call_gemini_json",
) -> dict:
    """
    Generate JSON-structured content using the full LLM provider chain with automatic fallback.
    """
    result, used = await call_llm_json(
        prompt=prompt,
        system_instruction=system_instruction or "",
        temperature=temperature,
        context=context,
    )
    if result is None:
        raise RuntimeError(f"All LLM providers failed (context={context})")
    return result


async def call_gemini_with_thoughts(
    prompt: str,
    system_instruction: Optional[str] = None,
    temperature: float = 1.0,
) -> Tuple[str, str]:
    """
    Generate content and return thinking process.

    Note: Fallback chain is used. Thinking data is only available from Gemini;
    other providers return empty string for the thinking field.
    """
    # Thinking requires direct provider call (chain doesn't propagate thinking field)
    # Try primary first, fall back to chain for content-only
    try:
        provider = _get_provider()
        response = await provider.generate_text(
            prompt=prompt,
            system_instruction=system_instruction,
            temperature=temperature,
            max_tokens=8192
        )
        return response.content, response.thinking or ""
    except Exception as e:
        logger.warning(f"Primary provider failed for thinking call: {e}, falling back to chain")
        result = await call_gemini(prompt=prompt, system_instruction=system_instruction,
                                    temperature=temperature, context="call_gemini_with_thoughts")
        return result, ""


async def call_gemini_with_search(
    prompt: str,
    system_instruction: Optional[str] = None,
    temperature: float = 1.0,
) -> str:
    """
    Generate content with Google Search grounding enabled.

    This is a backward compatibility function.

    IMPORTANT: This feature is only available when using Gemini provider.
    If LLM_PROVIDER=openai, this function will raise NotImplementedError.

    Args:
        prompt: User prompt
        system_instruction: Optional system context
        temperature: Sampling temperature (default 1.0)

    Returns:
        Generated text with grounded information

    Raises:
        LLMAuthError: If API key is invalid
        LLMRateLimitError: If rate limit is exceeded
        LLMTimeoutError: If request times out
        NotImplementedError: If using OpenAI provider (doesn't support web search)
    """
    provider = _get_provider()
    response = await provider.generate_with_search(
        prompt=prompt,
        system_instruction=system_instruction,
        temperature=temperature
    )
    return response.content
