"""Async Anthropic SDK wrapper for generate and stream calls."""

from collections.abc import AsyncGenerator

import anthropic


class LLMClient:
    """Thin wrapper around the Anthropic SDK."""

    # Sonnet 5 thinks by default when `thinking` is omitted (Sonnet 4 didn't).
    # Thinking counts against max_tokens, and our callers use small limits
    # (512-1024), so keep it off explicitly to preserve the old behavior.
    THINKING = {"type": "disabled"}

    def __init__(self, api_key: str, model: str = "claude-sonnet-5") -> None:
        self.model = model
        self.client = anthropic.AsyncAnthropic(api_key=api_key)

    def _split_messages(self, messages: list[dict]) -> tuple[str, list[dict]]:
        """Extract system message from the messages list.

        The Anthropic API takes system as a separate parameter.
        """
        system = ""
        user_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system = msg["content"]
            else:
                user_messages.append(msg)
        return system, user_messages

    async def generate(self, messages: list[dict], max_tokens: int = 1024) -> str:
        """Non-streaming call. Returns the full text response."""
        system, user_messages = self._split_messages(messages)
        response = await self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=user_messages,
            thinking=self.THINKING,
        )
        return response.content[0].text

    async def stream(
        self, messages: list[dict], max_tokens: int = 1024
    ) -> AsyncGenerator[str, None]:
        """Streaming call. Yields text deltas as they arrive."""
        system, user_messages = self._split_messages(messages)
        async with self.client.messages.stream(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=user_messages,
            thinking=self.THINKING,
        ) as stream:
            async for text in stream.text_stream:
                yield text
