"""
OpenAI Provider - LLM Provider implementation for OpenAI API

This class implements the LLMProvider interface for OpenAI Chat Completions API.
Supports OpenAI-compatible APIs (OpenAI, Kimi, etc.)
"""

import asyncio
import httpx
import json
import logging
from typing import Dict, Any, Optional

from .llm_provider import LLMProvider, LLMResponse, LLMAuthError, LLMRateLimitError, LLMTimeoutError

logger = logging.getLogger(__name__)

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds


class OpenAIProvider(LLMProvider):
    """OpenAI Chat Completions Provider."""

    def __init__(self, api_key: str, model: str, api_url: Optional[str] = None):
        self.api_key = api_key
        self.model = model
        self.api_url = api_url or "https://api.openai.com/v1/chat/completions"

        if not self.api_key:
            raise LLMAuthError("OPENAI_API_KEY not set")

        logger.info(f"OpenAI Provider initialized: model={self.model}, url={self.api_url}")

    async def generate_text(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 1.0,
        max_tokens: int = 8192
    ) -> LLMResponse:
        """Generate text response with OpenAI."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        # 检测是否为 Kimi/Moonshot API
        is_kimi_api = "moonshot" in self.api_url.lower()

        # Build messages array
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        # Thinking models (kimi-k2, o1, etc.) only accept temperature=1
        _model_lower = self.model.lower()
        is_thinking_model = any(k in _model_lower for k in ("k2", "thinking", "o1", "o3"))
        effective_temp = 1.0 if is_thinking_model else temperature

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": effective_temp,
            "max_tokens": max_tokens
        }

        timeout_seconds = 180.0 if is_kimi_api else 60.0

        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        self.api_url,
                        json=payload,
                        headers=headers,
                        timeout=timeout_seconds
                    )
                    response.raise_for_status()
                    result = response.json()

                    # Extract response content
                    content = result["choices"][0]["message"]["content"]

                    # Extract token usage (OpenAI provides this natively)
                    usage_data = result.get("usage", {})
                    usage = {
                        "prompt_tokens": usage_data.get("prompt_tokens", 0),
                        "completion_tokens": usage_data.get("completion_tokens", 0),
                        "total_tokens": usage_data.get("total_tokens", 0)
                    }

                    # Log token usage
                    logger.info(f"OpenAI API usage - prompt: {usage['prompt_tokens']}, "
                               f"completion: {usage['completion_tokens']}, "
                               f"total: {usage['total_tokens']} tokens")

                    return LLMResponse(
                        content=content,
                        thinking=None,  # OpenAI doesn't support thinking mode
                        usage=usage
                    )

            except (httpx.RemoteProtocolError, httpx.ConnectError, httpx.ReadError) as e:
                last_error = e
                if attempt < MAX_RETRIES - 1:
                    logger.warning(f"OpenAI network error (attempt {attempt + 1}/{MAX_RETRIES}): {e}")
                    await asyncio.sleep(RETRY_DELAY * (attempt + 1))
                else:
                    logger.error(f"OpenAI network error after {MAX_RETRIES} attempts: {e}")
                    raise LLMTimeoutError(f"OpenAI API timeout: {e}")

            except httpx.HTTPStatusError as e:
                status_code = e.response.status_code
                response_text = e.response.text

                if status_code in [400, 401]:
                    raise LLMAuthError(f"Invalid OpenAI API key: {response_text}")
                elif status_code == 429:
                    raise LLMRateLimitError(f"OpenAI rate limit exceeded: {response_text}")
                else:
                    logger.error(f"OpenAI HTTP error: {status_code} - {response_text}")
                    raise

            except httpx.TimeoutException as e:
                last_error = e
                if attempt < MAX_RETRIES - 1:
                    logger.warning(f"OpenAI timeout (attempt {attempt + 1}/{MAX_RETRIES}): {e}")
                    await asyncio.sleep(RETRY_DELAY * (attempt + 1))
                else:
                    logger.error(f"OpenAI timeout after {MAX_RETRIES} attempts: {e}")
                    raise LLMTimeoutError(f"OpenAI request timeout: {e}")

            except Exception as e:
                logger.error(f"Unexpected OpenAI error: {e}")
                raise

        if last_error:
            raise last_error

    async def generate_json(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.5
    ) -> Dict[str, Any]:
        """Generate structured JSON response with OpenAI."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        # 检测是否为 Kimi/Moonshot API（不支持 response_format 参数）
        is_kimi_api = "moonshot" in self.api_url.lower()

        # Build messages array
        messages = []
        if system_instruction:
            # 对 Kimi API，在 system instruction 中强调 JSON 输出要求
            if is_kimi_api:
                system_instruction = system_instruction + "\n\nIMPORTANT: You MUST respond with valid JSON only. No markdown, no code blocks, no extra text. Start with { and end with }."
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        _model_lower = self.model.lower()
        is_thinking_model = any(k in _model_lower for k in ("k2", "thinking", "o1", "o3"))
        effective_temp = 1.0 if is_thinking_model else temperature

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": effective_temp,
            "max_tokens": 8192,
        }

        # 只有非 Kimi API 才使用 response_format（Kimi 不支持此参数）
        if not is_kimi_api:
            payload["response_format"] = {"type": "json_object"}

        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                # Kimi K2 Thinking 模型需要更长的超时时间，普通模型使用较短超时
                timeout_seconds = 180.0 if is_kimi_api else 60.0
                
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        self.api_url,
                        json=payload,
                        headers=headers,
                        timeout=timeout_seconds
                    )
                    response.raise_for_status()
                    result = response.json()

                    # Extract token usage
                    usage_data = result.get("usage", {})
                    usage = {
                        "prompt_tokens": usage_data.get("prompt_tokens", 0),
                        "completion_tokens": usage_data.get("completion_tokens", 0),
                        "total_tokens": usage_data.get("total_tokens", 0)
                    }

                    # Log token usage for JSON generation
                    logger.info(f"OpenAI JSON API usage - prompt: {usage['prompt_tokens']}, "
                               f"completion: {usage['completion_tokens']}, "
                               f"total: {usage['total_tokens']} tokens")

                    # Extract JSON content
                    content = result["choices"][0]["message"]["content"]

                    # Parse JSON
                    try:
                        return json.loads(content)
                    except json.JSONDecodeError as e:
                        logger.warning(f"Initial JSON parse failed: {e}")
                        # Fallback 1: extract JSON from markdown code blocks
                        try:
                            if "```json" in content:
                                json_str = content.split("```json")[1].split("```")[0].strip()
                                return json.loads(json_str)
                            elif "```" in content:
                                json_str = content.split("```")[1].split("```")[0].strip()
                                return json.loads(json_str)
                        except (json.JSONDecodeError, IndexError) as e2:
                            logger.error(f"Markdown extraction failed: {e2}")

                        # Fallback 2: Return empty structure to prevent crash
                        logger.error(f"All JSON parsing failed. Response: {content[:300]}")
                        return {"error": "JSON parse failed", "raw_response": content[:500]}

            except (httpx.RemoteProtocolError, httpx.ConnectError, httpx.ReadError) as e:
                last_error = e
                if attempt < MAX_RETRIES - 1:
                    logger.warning(f"OpenAI JSON network error (attempt {attempt + 1}/{MAX_RETRIES}): {e}")
                    await asyncio.sleep(RETRY_DELAY * (attempt + 1))
                else:
                    logger.error(f"OpenAI JSON network error after {MAX_RETRIES} attempts: {e}")
                    raise LLMTimeoutError(f"OpenAI JSON API timeout: {e}")

            except httpx.HTTPStatusError as e:
                status_code = e.response.status_code
                response_text = e.response.text

                if status_code in [400, 401]:
                    raise LLMAuthError(f"Invalid OpenAI API key: {response_text}")
                elif status_code == 429:
                    raise LLMRateLimitError(f"OpenAI rate limit exceeded: {response_text}")
                else:
                    logger.error(f"OpenAI JSON HTTP error: {status_code} - {response_text}")
                    raise

            except httpx.TimeoutException as e:
                last_error = e
                if attempt < MAX_RETRIES - 1:
                    logger.warning(f"OpenAI JSON timeout (attempt {attempt + 1}/{MAX_RETRIES}): {e}")
                    await asyncio.sleep(RETRY_DELAY * (attempt + 1))
                else:
                    logger.error(f"OpenAI JSON timeout after {MAX_RETRIES} attempts: {e}")
                    raise LLMTimeoutError(f"OpenAI JSON request timeout: {e}")

            except Exception as e:
                logger.error(f"Unexpected OpenAI JSON error: {e}")
                raise

        if last_error:
            raise last_error

    async def generate_with_search(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.7
    ) -> LLMResponse:
        """
        Generate response with web search.

        Note: OpenAI doesn't support native web search.
        This method raises NotImplementedError.
        """
        raise NotImplementedError(
            "OpenAI does not support native web search. "
            "Use Gemini provider or integrate external search tools (Perplexity, Tavily)."
        )
