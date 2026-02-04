"""Tests for the LLM client wrapper (mocked Anthropic SDK)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestLLMClientGenerate:
    @pytest.mark.asyncio
    async def test_returns_text_response(self):
        from app.ai.client import LLMClient

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="This is a test response.")]

        with patch("app.ai.client.anthropic") as mock_anthropic:
            mock_client = AsyncMock()
            mock_client.messages.create.return_value = mock_response
            mock_anthropic.AsyncAnthropic.return_value = mock_client

            client = LLMClient(api_key="test-key")
            result = await client.generate(
                [
                    {"role": "system", "content": "You are helpful."},
                    {"role": "user", "content": "Hello"},
                ]
            )

        assert result == "This is a test response."

    @pytest.mark.asyncio
    async def test_passes_correct_model(self):
        from app.ai.client import LLMClient

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="ok")]

        with patch("app.ai.client.anthropic") as mock_anthropic:
            mock_client = AsyncMock()
            mock_client.messages.create.return_value = mock_response
            mock_anthropic.AsyncAnthropic.return_value = mock_client

            client = LLMClient(api_key="test-key", model="custom-model")
            await client.generate(
                [
                    {"role": "system", "content": "sys"},
                    {"role": "user", "content": "hi"},
                ]
            )

            call_kwargs = mock_client.messages.create.call_args.kwargs
            assert call_kwargs["model"] == "custom-model"

    @pytest.mark.asyncio
    async def test_extracts_system_from_messages(self):
        from app.ai.client import LLMClient

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="ok")]

        with patch("app.ai.client.anthropic") as mock_anthropic:
            mock_client = AsyncMock()
            mock_client.messages.create.return_value = mock_response
            mock_anthropic.AsyncAnthropic.return_value = mock_client

            client = LLMClient(api_key="test-key")
            await client.generate(
                [
                    {"role": "system", "content": "Be concise."},
                    {"role": "user", "content": "Analyze this."},
                ]
            )

            call_kwargs = mock_client.messages.create.call_args.kwargs
            assert call_kwargs["system"] == "Be concise."
            # Only user messages in the messages param
            assert len(call_kwargs["messages"]) == 1
            assert call_kwargs["messages"][0]["role"] == "user"


def _make_stream_mock(mock_client, chunks):
    """Set up mock_client.messages.stream to yield chunks."""

    async def mock_text_stream():
        for chunk in chunks:
            yield chunk

    mock_stream_obj = MagicMock()
    mock_stream_obj.text_stream = mock_text_stream()

    # stream() returns a sync context manager in the Anthropic SDK
    mock_stream_ctx = MagicMock()
    mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_stream_obj)
    mock_stream_ctx.__aexit__ = AsyncMock(return_value=False)

    # Make stream() return the ctx directly (not a coroutine)
    mock_client.messages.stream = MagicMock(return_value=mock_stream_ctx)


class TestLLMClientStream:
    @pytest.mark.asyncio
    async def test_yields_text_chunks(self):
        from app.ai.client import LLMClient

        chunks = ["Hello ", "world", "!"]

        with patch("app.ai.client.anthropic") as mock_anthropic:
            mock_client = AsyncMock()
            _make_stream_mock(mock_client, chunks)
            mock_anthropic.AsyncAnthropic.return_value = mock_client

            client = LLMClient(api_key="test-key")
            collected = []
            async for text in client.stream(
                [
                    {"role": "system", "content": "sys"},
                    {"role": "user", "content": "hi"},
                ]
            ):
                collected.append(text)

        assert collected == chunks

    @pytest.mark.asyncio
    async def test_stream_passes_system_separately(self):
        from app.ai.client import LLMClient

        with patch("app.ai.client.anthropic") as mock_anthropic:
            mock_client = AsyncMock()
            _make_stream_mock(mock_client, ["ok"])
            mock_anthropic.AsyncAnthropic.return_value = mock_client

            client = LLMClient(api_key="test-key")
            async for _ in client.stream(
                [
                    {"role": "system", "content": "System msg"},
                    {"role": "user", "content": "User msg"},
                ]
            ):
                pass

            call_kwargs = mock_client.messages.stream.call_args.kwargs
            assert call_kwargs["system"] == "System msg"
            assert len(call_kwargs["messages"]) == 1
            assert call_kwargs["messages"][0]["role"] == "user"
