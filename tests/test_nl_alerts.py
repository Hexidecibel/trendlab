"""Tests for natural language alert intent detection."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.ai.query_parser import _handle_alert, parse_and_resolve
from app.models.schemas import (
    NaturalAlertResponse,
    NaturalQueryError,
    NaturalQueryResponse,
)

MOCK_LOOKUP_ITEMS = [
    SimpleNamespace(value="jYQJ19EqGR", label="Seattle Sounders FC"),
    SimpleNamespace(value="kaDQ0wRqEv", label="LA Galaxy"),
]


def _field(name, field_type, depends_on=None, label=None):
    """Create a mock form field."""
    return SimpleNamespace(
        name=name,
        field_type=field_type,
        depends_on=depends_on,
        label=label or name,
    )


class TestAlertIntentDetection:
    """Alert intent should be detected for future-intent phrases."""

    @pytest.mark.asyncio
    async def test_alert_intent_bitcoin_above(self):
        llm_response = json.dumps(
            {
                "alert": True,
                "source": "crypto",
                "fields": {"query": "bitcoin"},
                "threshold_direction": "above",
                "threshold_value": 50000,
                "name": "Bitcoin above $50,000",
                "interpretation": "Alert when Bitcoin exceeds $50,000",
            }
        )

        mock_client = MagicMock()
        mock_client.generate = AsyncMock(return_value=llm_response)

        result = await parse_and_resolve(
            "alert me when bitcoin goes above 50000",
            mock_client,
        )

        assert isinstance(result, NaturalAlertResponse)
        assert result.alert is True
        assert result.source == "crypto"
        assert result.query == "bitcoin"
        assert result.threshold_direction == "above"
        assert result.threshold_value == 50000
        assert result.name == "Bitcoin above $50,000"

    @pytest.mark.asyncio
    async def test_non_alert_passthrough(self):
        """Regular queries should not trigger alert flow."""
        llm_response = json.dumps(
            {
                "source": "crypto",
                "fields": {"query": "bitcoin"},
                "horizon": 14,
                "start": None,
                "end": None,
                "interpretation": "Bitcoin price",
            }
        )

        mock_client = MagicMock()
        mock_client.generate = AsyncMock(return_value=llm_response)

        result = await parse_and_resolve(
            "show me bitcoin price", mock_client
        )

        assert isinstance(result, NaturalQueryResponse)
        assert result.alert is False
        assert result.source == "crypto"

    @pytest.mark.asyncio
    async def test_past_tense_not_alert(self):
        """Past tense should produce a regular query, not an alert."""
        llm_response = json.dumps(
            {
                "source": "crypto",
                "fields": {"query": "bitcoin"},
                "horizon": 14,
                "start": None,
                "end": None,
                "interpretation": "Bitcoin price history",
            }
        )

        mock_client = MagicMock()
        mock_client.generate = AsyncMock(return_value=llm_response)

        result = await parse_and_resolve(
            "show me when bitcoin went above 50000",
            mock_client,
        )

        assert isinstance(result, NaturalQueryResponse)
        assert result.alert is False


class TestThresholdExtraction:
    """Test threshold value and direction parsing."""

    @pytest.mark.asyncio
    async def test_threshold_50k(self):
        llm_response = json.dumps(
            {
                "alert": True,
                "source": "crypto",
                "fields": {"query": "bitcoin"},
                "threshold_direction": "above",
                "threshold_value": 50000,
                "name": "Bitcoin above 50k",
                "interpretation": "Alert for Bitcoin above 50k",
            }
        )

        mock_client = MagicMock()
        mock_client.generate = AsyncMock(return_value=llm_response)

        result = await parse_and_resolve(
            "alert me when bitcoin goes above 50k",
            mock_client,
        )

        assert isinstance(result, NaturalAlertResponse)
        assert result.threshold_value == 50000

    @pytest.mark.asyncio
    async def test_threshold_1m(self):
        llm_response = json.dumps(
            {
                "alert": True,
                "source": "pypi",
                "fields": {"query": "fastapi"},
                "threshold_direction": "below",
                "threshold_value": 1000000,
                "name": "FastAPI downloads below 1M",
                "interpretation": "Alert for FastAPI below 1M",
            }
        )

        mock_client = MagicMock()
        mock_client.generate = AsyncMock(return_value=llm_response)

        result = await parse_and_resolve(
            "tell me when fastapi downloads drop below 1M",
            mock_client,
        )

        assert isinstance(result, NaturalAlertResponse)
        assert result.threshold_value == 1000000

    @pytest.mark.asyncio
    async def test_direction_above(self):
        llm_response = json.dumps(
            {
                "alert": True,
                "source": "crypto",
                "fields": {"query": "ethereum"},
                "threshold_direction": "above",
                "threshold_value": 5000,
                "name": "Ethereum above $5,000",
                "interpretation": "Alert when Ethereum exceeds $5,000",
            }
        )

        mock_client = MagicMock()
        mock_client.generate = AsyncMock(return_value=llm_response)

        result = await parse_and_resolve(
            "notify me when ethereum exceeds 5000",
            mock_client,
        )

        assert isinstance(result, NaturalAlertResponse)
        assert result.threshold_direction == "above"

    @pytest.mark.asyncio
    async def test_direction_below(self):
        llm_response = json.dumps(
            {
                "alert": True,
                "source": "crypto",
                "fields": {"query": "bitcoin"},
                "threshold_direction": "below",
                "threshold_value": 30000,
                "name": "Bitcoin below $30,000",
                "interpretation": "Alert when Bitcoin drops below $30k",
            }
        )

        mock_client = MagicMock()
        mock_client.generate = AsyncMock(return_value=llm_response)

        result = await parse_and_resolve(
            "let me know when bitcoin drops below 30000",
            mock_client,
        )

        assert isinstance(result, NaturalAlertResponse)
        assert result.threshold_direction == "below"


class TestHandleAlert:
    """Tests for _handle_alert helper."""

    @pytest.mark.asyncio
    async def test_valid_alert(self):
        parsed = {
            "alert": True,
            "source": "crypto",
            "fields": {"query": "bitcoin"},
            "threshold_direction": "above",
            "threshold_value": 50000,
            "name": "Bitcoin above $50,000",
            "interpretation": "Alert when Bitcoin exceeds $50k",
        }
        result = await _handle_alert(parsed)
        assert isinstance(result, NaturalAlertResponse)
        assert result.source == "crypto"
        assert result.query == "bitcoin"
        assert result.threshold_direction == "above"
        assert result.threshold_value == 50000
        assert result.alert is True

    @pytest.mark.asyncio
    async def test_unknown_source(self):
        parsed = {
            "alert": True,
            "source": "nonexistent",
            "fields": {"query": "test"},
            "threshold_direction": "above",
            "threshold_value": 100,
            "name": "Test alert",
            "interpretation": "Test",
        }
        result = await _handle_alert(parsed)
        assert isinstance(result, NaturalQueryError)
        assert "Unknown data source" in result.error

    @pytest.mark.asyncio
    async def test_entity_resolution_in_alert(self):
        mock_adapter = MagicMock()
        mock_adapter.form_fields.return_value = [
            _field("league", "select"),
            _field(
                "entity",
                "autocomplete",
                depends_on="league",
            ),
            _field("metric", "select"),
            _field("home_away", "select"),
            _field("stage", "select"),
        ]
        mock_adapter.lookup = AsyncMock(
            return_value=[
                SimpleNamespace(
                    value="jYQJ19EqGR",
                    label="Seattle Sounders FC",
                ),
            ]
        )

        parsed = {
            "alert": True,
            "source": "asa",
            "fields": {
                "league": "mls",
                "entity": "Seattle Sounders FC",
                "metric": "xgoals_for",
                "home_away": "all",
                "stage": "regular",
            },
            "threshold_direction": "above",
            "threshold_value": 2.0,
            "name": "Sounders xG above 2.0",
            "interpretation": "Alert for Sounders xG above 2.0",
        }

        with patch(
            "app.ai.query_parser.registry"
        ) as mock_registry:
            mock_registry.get.return_value = mock_adapter
            result = await _handle_alert(parsed)

        assert isinstance(result, NaturalAlertResponse)
        assert "jYQJ19EqGR" in result.query

    @pytest.mark.asyncio
    async def test_entity_resolution_failure(self):
        mock_adapter = MagicMock()
        mock_adapter.form_fields.return_value = [
            _field(
                "entity",
                "autocomplete",
                label="Team",
            ),
        ]
        mock_adapter.lookup = AsyncMock(
            return_value=[
                SimpleNamespace(
                    value="abc",
                    label="Some Team",
                ),
            ]
        )

        parsed = {
            "alert": True,
            "source": "asa",
            "fields": {"entity": "Nonexistent FC"},
            "threshold_direction": "above",
            "threshold_value": 1.0,
            "name": "Test",
            "interpretation": "Test",
        }

        with patch(
            "app.ai.query_parser.registry"
        ) as mock_registry:
            mock_registry.get.return_value = mock_adapter
            result = await _handle_alert(parsed)

        assert isinstance(result, NaturalQueryError)
        assert "Could not resolve" in result.error
