"""
LLM Factory - Multi-provider chain with automatic fallback

Reads LLM_CHAIN from config (built from LLM_PROVIDERS env var).
Each provider gets 2 attempts (normal temp + lower temp retry).
Providers are tried in order until one succeeds.
"""

import logging
import asyncio
from typing import Optional, Tuple, Any, List

from .llm_provider import LLMProvider
from .gemini_provider import GeminiProvider
from .openai_provider import OpenAIProvider

logger = logging.getLogger(__name__)

RETRY_DELAY_SECONDS = 2

_provider_cache: dict = {}


class LLMFactory:
    """Factory that creates and caches provider instances from LLM_CHAIN."""

    @staticmethod
    def _get_chain() -> list:
        from config import LLM_CHAIN
        return LLM_CHAIN

    @staticmethod
    def create_provider(entry: dict) -> LLMProvider:
        """Create a provider instance from a chain entry dict."""
        ptype = entry["type"]
        if ptype == "gemini":
            return GeminiProvider(
                api_key=entry["api_key"],
                model=entry["model"],
                api_url=entry["api_url"] or None,
            )
        else:
            return OpenAIProvider(
                api_key=entry["api_key"],
                model=entry["model"],
                api_url=entry["api_url"] or None,
            )

    @staticmethod
    def get_provider_by_index(idx: int) -> Optional[LLMProvider]:
        """Get (or create & cache) the provider at position *idx* in the chain."""
        chain = LLMFactory._get_chain()
        if idx < 0 or idx >= len(chain):
            return None
        key = chain[idx]["name"]
        if key not in _provider_cache:
            try:
                _provider_cache[key] = LLMFactory.create_provider(chain[idx])
            except Exception as e:
                logger.warning(f"Failed to create provider '{key}': {e}")
                return None
        return _provider_cache[key]

    @staticmethod
    def get_provider() -> LLMProvider:
        """Get the first (primary) provider. Backward-compatible."""
        p = LLMFactory.get_provider_by_index(0)
        if p is None:
            raise RuntimeError("No LLM provider available")
        return p

    @staticmethod
    def get_provider_name() -> str:
        chain = LLMFactory._get_chain()
        return chain[0]["name"] if chain else "unknown"

    @staticmethod
    def get_fallback_provider() -> Optional[LLMProvider]:
        """Backward-compatible: returns second provider if exists."""
        return LLMFactory.get_provider_by_index(1)

    @staticmethod
    def get_fallback_provider_name() -> Optional[str]:
        chain = LLMFactory._get_chain()
        return chain[1]["name"] if len(chain) > 1 else None

    @staticmethod
    def reset():
        global _provider_cache
        _provider_cache = {}


# Backward-compatible convenience functions
def get_llm() -> LLMProvider:
    return LLMFactory.get_provider()


def get_fallback_llm() -> Optional[LLMProvider]:
    return LLMFactory.get_fallback_provider()


# =============================================================================
# Unified LLM Call with Chain Fallback
# =============================================================================

async def call_llm_with_retry(
    prompt: str,
    system_instruction: str = "",
    response_type: str = "json",
    temperature: float = 1.0,
    context: str = "unknown",
) -> Tuple[Any, str]:
    """
    Call LLM with automatic retry across the full provider chain.

    For each provider in LLM_CHAIN:
      attempt 1: normal temperature
      attempt 2: lower temperature retry
    Moves to next provider on failure.
    """
    chain = LLMFactory._get_chain()
    retry_temp = max(0.3, temperature - 0.2)

    attempts: list = []
    for idx, entry in enumerate(chain):
        name = entry["name"]
        attempts.append((idx, temperature, name))
        attempts.append((idx, retry_temp, f"{name} retry"))

    last_error = None
    total = len(attempts)

    for i, (provider_idx, temp, description) in enumerate(attempts):
        try:
            provider = LLMFactory.get_provider_by_index(provider_idx)
            if provider is None:
                logger.warning(f"[{context}] Attempt {i+1}/{total}: Provider '{description}' not available")
                continue

            logger.info(f"[{context}] Attempt {i+1}/{total}: Calling {description} (temp={temp})")

            if response_type == "json":
                result = await provider.generate_json(
                    prompt=prompt,
                    system_instruction=system_instruction,
                    temperature=temp,
                )
            else:
                result = await provider.generate_text(
                    prompt=prompt,
                    system_instruction=system_instruction if system_instruction else None,
                    temperature=temp,
                )

            # Validate response
            if response_type == "json":
                if isinstance(result, dict) and "error" in result:
                    error_msg = result.get("error", "Unknown error")
                    logger.warning(f"[{context}] Attempt {i+1}: {description} returned error: {error_msg}")
                    last_error = error_msg
                    if i < total - 1:
                        await asyncio.sleep(RETRY_DELAY_SECONDS)
                    continue
            else:
                if hasattr(result, "content"):
                    result = result.content
                if not result or (isinstance(result, str) and result.startswith("Error")):
                    logger.warning(f"[{context}] Attempt {i+1}: {description} returned invalid: {str(result)[:100]}")
                    last_error = str(result)[:100] if result else "empty response"
                    if i < total - 1:
                        await asyncio.sleep(RETRY_DELAY_SECONDS)
                    continue

            logger.info(f"[{context}] LLM call succeeded on attempt {i+1} using {description}")
            return result, description

        except Exception as e:
            last_error = str(e)
            logger.warning(f"[{context}] Attempt {i+1}: {description} failed: {e}")
            if i < total - 1:
                await asyncio.sleep(RETRY_DELAY_SECONDS)

    logger.error(f"[{context}] All {total} LLM attempts failed. Last error: {last_error}")
    return None, "all_failed"


async def call_llm_json(
    prompt: str,
    system_instruction: str = "",
    temperature: float = 1.0,
    context: str = "unknown",
) -> Tuple[Any, str]:
    """Convenience wrapper: call LLM expecting JSON response."""
    return await call_llm_with_retry(
        prompt=prompt,
        system_instruction=system_instruction,
        response_type="json",
        temperature=temperature,
        context=context,
    )


async def call_llm_text(
    prompt: str,
    system_instruction: str = "",
    temperature: float = 0.7,
    context: str = "unknown",
) -> Tuple[Optional[str], str]:
    """Convenience wrapper: call LLM expecting text response."""
    return await call_llm_with_retry(
        prompt=prompt,
        system_instruction=system_instruction,
        response_type="text",
        temperature=temperature,
        context=context,
    )
