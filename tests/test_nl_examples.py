"""Tests for NL example queries shown in the UI help section."""

import pytest

from app.ai.query_parser import parse_and_resolve
from app.models.schemas import (
    NaturalCompareResponse,
    NaturalQueryError,
    NaturalQueryResponse,
)

# Example queries from NaturalQueryInput.tsx
EXAMPLE_QUERIES = [
    # Sports - MLS
    ("Seattle Sounders vs Portland Timbers xG this season", "compare"),
    ("LAFC expected goals at home, monthly", "single"),
    ("Inter Miami xPass completion by season", "single"),
    ("Compare Seattle Sounders and LAFC xGoals this season", "compare"),
    # Stocks & Finance
    ("Tesla stock price last 6 months, weekly", "single"),
    ("Compare Apple and Microsoft stock prices this year", "compare"),
    ("Bitcoin vs Ethereum price last 3 months, normalized", "compare"),
    ("NVIDIA trading volume last quarter", "single"),
    # Tech & Open Source
    ("FastAPI downloads this year with rolling average", "single"),
    ("Compare pandas and numpy downloads monthly", "compare"),
    ("Python requests library weekly downloads", "single"),
    # Wikipedia & Culture
    ("ChatGPT Wikipedia views last 90 days", "single"),
    ("Compare Python and JavaScript Wikipedia page views", "compare"),
    ("Taylor Swift Wikipedia traffic last 30 days", "single"),
    # Weather
    ("Seattle temperature last 90 days", "single"),
    ("Compare New York and Los Angeles temperature monthly", "compare"),
    ("Miami precipitation last 6 months", "single"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("query,expected_type", EXAMPLE_QUERIES)
async def test_example_query_parses(query: str, expected_type: str):
    """Test that each example query parses successfully without errors."""
    result = await parse_and_resolve(query)

    # Should not be an error
    assert not isinstance(result, NaturalQueryError), (
        f"Query '{query}' failed: {result.error}"
    )

    # Check correct response type
    if expected_type == "compare":
        assert isinstance(result, NaturalCompareResponse), (
            f"Expected compare response for '{query}'"
        )
        assert len(result.items) >= 2, f"Compare should have 2+ items for '{query}'"
    else:
        assert isinstance(result, NaturalQueryResponse), (
            f"Expected single response for '{query}'"
        )
        assert result.source, f"Missing source for '{query}'"
        assert result.query, f"Missing query string for '{query}'"


# Test individual adapters to ensure they resolve correctly
@pytest.mark.asyncio
async def test_pypi_query():
    """Test PyPI adapter query."""
    result = await parse_and_resolve("FastAPI downloads this year")
    assert isinstance(result, NaturalQueryResponse)
    assert result.source == "pypi"
    assert "fastapi" in result.query.lower()


@pytest.mark.asyncio
async def test_crypto_query():
    """Test crypto adapter query."""
    result = await parse_and_resolve("Bitcoin price last 30 days")
    assert isinstance(result, NaturalQueryResponse)
    assert result.source == "crypto"
    assert "bitcoin" in result.query.lower()


@pytest.mark.asyncio
async def test_wikipedia_query():
    """Test Wikipedia adapter query - entity resolution."""
    result = await parse_and_resolve("Python programming language Wikipedia views")
    assert isinstance(result, NaturalQueryResponse)
    assert result.source == "wikipedia"
    # Query should be colon-separated with article name
    assert ":" in result.query


@pytest.mark.asyncio
async def test_stocks_query():
    """Test stocks adapter query."""
    result = await parse_and_resolve("TSLA stock price")
    assert isinstance(result, NaturalQueryResponse)
    assert result.source == "stocks"
    # Stocks adapter uses ticker symbols directly
    assert "TSLA" in result.query or "tsla" in result.query.lower()


@pytest.mark.asyncio
async def test_weather_query():
    """Test weather adapter query."""
    result = await parse_and_resolve("Seattle temperature")
    assert isinstance(result, NaturalQueryResponse)
    assert result.source == "weather"
    # Weather uses coordinates, not city name - just verify it resolved
    assert ":" in result.query  # Colon-separated format


@pytest.mark.asyncio
async def test_asa_teams_query():
    """Test ASA adapter with teams."""
    result = await parse_and_resolve("Seattle Sounders xG")
    assert isinstance(result, NaturalQueryResponse)
    assert result.source == "asa"
    # Should have resolved team name to ID
    assert ":" in result.query


@pytest.mark.asyncio
async def test_compare_same_source():
    """Test comparison within same source."""
    result = await parse_and_resolve("Compare fastapi and django downloads")
    assert isinstance(result, NaturalCompareResponse)
    assert len(result.items) == 2
    assert all(item.source == "pypi" for item in result.items)


@pytest.mark.asyncio
async def test_resample_detection():
    """Test that resample keywords are detected."""
    result = await parse_and_resolve("FastAPI downloads monthly")
    assert isinstance(result, NaturalQueryResponse)
    assert result.resample == "month"


@pytest.mark.asyncio
async def test_apply_detection():
    """Test that transform keywords are detected."""
    result = await parse_and_resolve("FastAPI downloads with rolling average")
    assert isinstance(result, NaturalQueryResponse)
    assert result.apply is not None
    assert "rolling" in result.apply.lower()
