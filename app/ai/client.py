"""Async Anthropic SDK wrapper for generate and stream calls."""

from collections.abc import AsyncGenerator

import anthropic


class LLMClient:
    """Thin wrapper around the Anthropic SDK."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514") -> None:
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
        ) as stream:
            async for text in stream.text_stream:
                yield text
