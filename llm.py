"""LLM client — supports OpenAI-compatible and Anthropic-compatible APIs."""

import asyncio
from openai import AsyncOpenAI
from anthropic import AsyncAnthropic


class LLMClient:
    """Unified async LLM client for OpenAI / Anthropic protocols."""

    def __init__(self, provider: str = "openai", api_key: str = "",
                 base_url: str = "", model: str = ""):
        self.provider = provider
        self.model = model
        self.total_input_tokens = 0
        self.total_output_tokens = 0

        if provider == "anthropic":
            kwargs = {"api_key": api_key}
            if base_url:
                kwargs["base_url"] = base_url
            self.client = AsyncAnthropic(**kwargs)
        else:
            kwargs = {"api_key": api_key}
            if base_url:
                kwargs["base_url"] = base_url
            self.client = AsyncOpenAI(**kwargs)

    async def call(self, prompt: str, system: str = "",
                   temperature: float = 0.7, max_tokens: int = 8192,
                   json_mode: bool = False) -> str:
        """Single LLM call with retry on rate limit."""
        if self.provider == "anthropic":
            return await self._call_anthropic(prompt, system, temperature, max_tokens)
        return await self._call_openai(prompt, system, temperature, max_tokens, json_mode)

    async def _call_openai(self, prompt, system, temperature, max_tokens, json_mode):
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        for attempt in range(3):
            try:
                resp = await self.client.chat.completions.create(**kwargs)
                usage = resp.usage
                if usage:
                    self.total_input_tokens += usage.prompt_tokens
                    self.total_output_tokens += usage.completion_tokens
                return resp.choices[0].message.content
            except Exception as e:
                err_str = str(e).lower()
                if "rate" in err_str or "429" in err_str:
                    wait = (2 ** attempt) * 2
                    print(f"  ⏳ 限流，等待 {wait}s ...")
                    await asyncio.sleep(wait)
                elif attempt < 2:
                    print(f"  ⚠️  请求失败({e})，重试 ...")
                    await asyncio.sleep(1)
                else:
                    raise
        return ""

    async def _call_anthropic(self, prompt, system, temperature, max_tokens):
        """Anthropic protocol: system is a top-level param, no system role in messages."""
        kwargs = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system
        # Anthropic doesn't support temperature with all models; try anyway
        try:
            kwargs["temperature"] = temperature
        except Exception:
            pass

        for attempt in range(3):
            try:
                resp = await self.client.messages.create(**kwargs)
                if hasattr(resp, "usage") and resp.usage:
                    self.total_input_tokens += resp.usage.input_tokens
                    self.total_output_tokens += resp.usage.output_tokens
                # Extract text from content blocks
                text_parts = []
                for block in resp.content:
                    if hasattr(block, "text"):
                        text_parts.append(block.text)
                return "\n".join(text_parts)
            except Exception as e:
                err_str = str(e).lower()
                if "rate" in err_str or "429" in err_str:
                    wait = (2 ** attempt) * 2
                    print(f"  ⏳ 限流，等待 {wait}s ...")
                    await asyncio.sleep(wait)
                elif attempt < 2:
                    print(f"  ⚠️  请求失败({e})，重试 ...")
                    await asyncio.sleep(1)
                else:
                    raise
        return ""

    def get_cost_estimate(self, input_price: float = 0.27, output_price: float = 1.10) -> float:
        """Estimate cost in USD. Defaults are DeepSeek pricing per 1M tokens."""
        return (self.total_input_tokens * input_price +
                self.total_output_tokens * output_price) / 1_000_000

    def reset_stats(self):
        self.total_input_tokens = 0
        self.total_output_tokens = 0
