"""Tests for the natural language query parser."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.ai.query_parser import (
    _extract_json,
    _find_best_match,
    _handle_compare,
    build_catalog_prompt,
    build_query_string,
    parse_and_resolve,
    resolve_entities,
)
from app.models.schemas import (
    LookupItem,
    NaturalCompareResponse,
    NaturalQueryError,
    NaturalQueryResponse,
)

MOCK_LOOKUP_ITEMS = [
    LookupItem(value="jYQJ19EqGR", label="Seattle Sounders FC"),
    LookupItem(value="kaDQ0wRqEv", label="LA Galaxy"),
    LookupItem(value="abc123", label="Inter Miami CF"),
    LookupItem(value="def456", label="New York City FC"),
]


def _field(name, field_type, depends_on=None, label=None):
    """Create a mock form field (MagicMock(name=...) doesn't set .name)."""
    return SimpleNamespace(
        name=name,
        field_type=field_type,
        depends_on=depends_on,
        label=label or name,
    )


class TestBuildCatalogPrompt:
    def test_includes_registered_sources(self):
        catalog = build_catalog_prompt()
        # At minimum pypi and crypto are always registered
        assert "pypi" in catalog
        assert "crypto" in catalog

    def test_includes_field_options(self):
        catalog = build_catalog_prompt()
        # ASA has metric options
        assert "goals_for" in catalog or "asa" in catalog

    def test_includes_query_format(self):
        catalog = build_catalog_prompt()
        assert "Query format" in catalog


class TestFindBestMatch:
    def test_exact_match(self):
        match = _find_best_match("Seattle Sounders FC", MOCK_LOOKUP_ITEMS)
        assert match is not None
        assert match.value == "jYQJ19EqGR"

    def test_exact_match_case_insensitive(self):
        match = _find_best_match("seattle sounders fc", MOCK_LOOKUP_ITEMS)
        assert match is not None
        assert match.value == "jYQJ19EqGR"

    def test_substring_match(self):
        match = _find_best_match("Sounders", MOCK_LOOKUP_ITEMS)
        assert match is not None
        assert match.value == "jYQJ19EqGR"

    def test_substring_match_label_in_query(self):
        match = _find_best_match("the LA Galaxy team", MOCK_LOOKUP_ITEMS)
        assert match is not None
        assert match.value == "kaDQ0wRqEv"

    def test_token_overlap_match(self):
        match = _find_best_match("Seattle FC", MOCK_LOOKUP_ITEMS)
        assert match is not None
        assert match.value == "jYQJ19EqGR"

    def test_no_match_returns_none(self):
        match = _find_best_match("Nonexistent Team", MOCK_LOOKUP_ITEMS)
        assert match is None

    def test_empty_query_returns_none(self):
        match = _find_best_match("", MOCK_LOOKUP_ITEMS)
        assert match is None

    def test_empty_items_returns_none(self):
        match = _find_best_match("Seattle", [])
        assert match is None


class TestBuildQueryString:
    def test_simple_adapter(self):
        """PyPI adapter has a single 'query' field."""
        result = build_query_string("pypi", {"query": "fastapi"})
        assert result == "fastapi"

    def test_complex_adapter(self):
        """ASA adapter joins fields with colons."""
        fields = {
            "league": "mls",
            "team": "jYQJ19EqGR",
            "metric": "xgoals_for",
            "home_away": "home",
            "stage": "regular",
        }
        result = build_query_string("asa", fields)
        assert result == "mls:jYQJ19EqGR:xgoals_for:home:regular"

    def test_field_order_matches_form_fields(self):
        """Fields should be joined in the order defined by form_fields."""
        fields = {
            "metric": "goals_for",
            "league": "nwsl",
            "team": "abc",
            "home_away": "all",
            "stage": "all",
        }
        result = build_query_string("asa", fields)
        # Order: league, team, metric, home_away, stage
        assert result == "nwsl:abc:goals_for:all:all"


class TestExtractJson:
    def test_plain_json(self):
        raw = '{"source": "pypi", "fields": {"query": "fastapi"}}'
        result = _extract_json(raw)
        assert result["source"] == "pypi"

    def test_json_with_markdown_fences(self):
        raw = '```\n{"source": "pypi"}\n```'
        result = _extract_json(raw)
        assert result["source"] == "pypi"

    def test_json_with_json_fence(self):
        raw = '```json\n{"source": "crypto"}\n```'
        result = _extract_json(raw)
        assert result["source"] == "crypto"

    def test_invalid_json_raises(self):
        with pytest.raises(json.JSONDecodeError):
            _extract_json("not json at all")

    def test_whitespace_handling(self):
        raw = '  \n  {"key": "value"}  \n  '
        result = _extract_json(raw)
        assert result["key"] == "value"


class TestResolveEntities:
    @pytest.mark.asyncio
    async def test_resolves_team_name_to_id(self):
        mock_adapter = MagicMock()
        mock_adapter.form_fields.return_value = [
            _field("league", "select"),
            _field("entity", "autocomplete", depends_on="league"),
        ]
        mock_adapter.lookup = AsyncMock(return_value=MOCK_LOOKUP_ITEMS)

        with patch("app.ai.query_parser.registry") as mock_registry:
            mock_registry.get.return_value = mock_adapter

            fields = {"league": "mls", "entity": "Seattle Sounders FC"}
            resolved = await resolve_entities("asa", fields)

            assert resolved["entity"] == "jYQJ19EqGR"
            assert resolved["league"] == "mls"  # unchanged

    @pytest.mark.asyncio
    async def test_passes_through_non_autocomplete_fields(self):
        mock_adapter = MagicMock()
        mock_adapter.form_fields.return_value = [
            _field("query", "text"),
        ]

        with patch("app.ai.query_parser.registry") as mock_registry:
            mock_registry.get.return_value = mock_adapter

            fields = {"query": "fastapi"}
            resolved = await resolve_entities("pypi", fields)
            assert resolved["query"] == "fastapi"

    @pytest.mark.asyncio
    async def test_raises_for_unresolvable_entity(self):
        mock_adapter = MagicMock()
        mock_adapter.form_fields.return_value = [
            _field("entity", "autocomplete", label="Team"),
        ]
        mock_adapter.lookup = AsyncMock(return_value=MOCK_LOOKUP_ITEMS)

        with patch("app.ai.query_parser.registry") as mock_registry:
            mock_registry.get.return_value = mock_adapter

            with pytest.raises(ValueError, match="Could not resolve"):
                await resolve_entities("asa", {"entity": "Nonexistent FC"})

    @pytest.mark.asyncio
    async def test_passes_depends_on_kwargs_to_lookup(self):
        mock_adapter = MagicMock()
        mock_adapter.form_fields.return_value = [
            _field("team", "autocomplete", depends_on="league"),
        ]
        mock_adapter.lookup = AsyncMock(return_value=MOCK_LOOKUP_ITEMS)

        with patch("app.ai.query_parser.registry") as mock_registry:
            mock_registry.get.return_value = mock_adapter

            await resolve_entities("asa", {"league": "mls", "team": "LA Galaxy"})
            mock_adapter.lookup.assert_called_once_with(
                "team", league="mls", search="LA Galaxy"
            )


class TestParseAndResolve:
    @pytest.mark.asyncio
    async def test_full_pipeline_pypi(self):
        llm_response = json.dumps(
            {
                "source": "pypi",
                "fields": {"query": "fastapi"},
                "horizon": 14,
                "start": None,
                "end": None,
                "interpretation": "PyPI downloads for fastapi",
            }
        )

        mock_client = MagicMock()
        mock_client.generate = AsyncMock(return_value=llm_response)

        result = await parse_and_resolve("show me fastapi downloads", mock_client)

        assert isinstance(result, NaturalQueryResponse)
        assert result.source == "pypi"
        assert result.query == "fastapi"
        assert result.horizon == 14
        assert result.interpretation == "PyPI downloads for fastapi"

    @pytest.mark.asyncio
    async def test_full_pipeline_asa(self):
        llm_response = json.dumps(
            {
                "source": "asa",
                "fields": {
                    "league": "mls",
                    "entity_type": "teams",
                    "entity": "Seattle Sounders FC",
                    "metric": "xgoals_for",
                    "home_away": "home",
                    "stage": "all",
                },
                "horizon": 14,
                "start": None,
                "end": None,
                "interpretation": "xG for Seattle Sounders at home",
            }
        )

        mock_client = MagicMock()
        mock_client.generate = AsyncMock(return_value=llm_response)

        # Mock the lookup for entity resolution
        mock_adapter = MagicMock()
        mock_adapter.form_fields.return_value = [
            _field("league", "select"),
            _field("entity_type", "select"),
            _field("entity", "autocomplete", depends_on="league"),
            _field("metric", "select"),
            _field("home_away", "select"),
            _field("stage", "select"),
        ]
        mock_adapter.lookup = AsyncMock(return_value=MOCK_LOOKUP_ITEMS)

        with patch("app.ai.query_parser.registry") as mock_registry:
            mock_registry.get.return_value = mock_adapter
            mock_registry.list_sources.return_value = []

            result = await parse_and_resolve("Seattle Sounders xG at home", mock_client)

        assert isinstance(result, NaturalQueryResponse)
        assert result.source == "asa"
        # Entity should be resolved to ID
        assert "jYQJ19EqGR" in result.query
        assert result.query == "mls:teams:jYQJ19EqGR:xgoals_for:home:all"

    @pytest.mark.asyncio
    async def test_llm_returns_error_json(self):
        llm_response = json.dumps(
            {
                "error": "Cannot parse this query",
                "suggestions": ["Try something else"],
            }
        )

        mock_client = MagicMock()
        mock_client.generate = AsyncMock(return_value=llm_response)

        result = await parse_and_resolve("gibberish", mock_client)

        assert isinstance(result, NaturalQueryError)
        assert "Cannot parse" in result.error
        assert len(result.suggestions) == 1

    @pytest.mark.asyncio
    async def test_llm_returns_unparseable_text(self):
        mock_client = MagicMock()
        mock_client.generate = AsyncMock(return_value="I don't understand your query")

        result = await parse_and_resolve("test", mock_client)

        assert isinstance(result, NaturalQueryError)
        assert "Failed to parse" in result.error

    @pytest.mark.asyncio
    async def test_unknown_source_in_llm_response(self):
        llm_response = json.dumps(
            {
                "source": "nonexistent",
                "fields": {"query": "test"},
                "horizon": 14,
                "start": None,
                "end": None,
                "interpretation": "test",
            }
        )

        mock_client = MagicMock()
        mock_client.generate = AsyncMock(return_value=llm_response)

        result = await parse_and_resolve("test", mock_client)

        assert isinstance(result, NaturalQueryError)
        assert "Unknown data source" in result.error

    @pytest.mark.asyncio
    async def test_entity_resolution_failure(self):
        llm_response = json.dumps(
            {
                "source": "asa",
                "fields": {
                    "league": "mls",
                    "entity_type": "teams",
                    "entity": "Nonexistent FC",
                    "metric": "goals_for",
                    "home_away": "all",
                    "stage": "all",
                },
                "horizon": 14,
                "start": None,
                "end": None,
                "interpretation": "test",
            }
        )

        mock_client = MagicMock()
        mock_client.generate = AsyncMock(return_value=llm_response)

        mock_adapter = MagicMock()
        mock_adapter.form_fields.return_value = [
            _field("league", "select"),
            _field("entity_type", "select"),
            _field("entity", "autocomplete", depends_on="league", label="Team"),
            _field("metric", "select"),
            _field("home_away", "select"),
            _field("stage", "select"),
        ]
        mock_adapter.lookup = AsyncMock(return_value=MOCK_LOOKUP_ITEMS)

        with patch("app.ai.query_parser.registry") as mock_registry:
            mock_registry.get.return_value = mock_adapter
            mock_registry.list_sources.return_value = []

            result = await parse_and_resolve("Nonexistent FC goals", mock_client)

        assert isinstance(result, NaturalQueryError)
        assert "Could not resolve" in result.error

    @pytest.mark.asyncio
    async def test_missing_api_key_raises(self):
        with patch("app.ai.query_parser.settings") as mock_settings:
            mock_settings.anthropic_api_key = None
            with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
                await parse_and_resolve("test", client=None)

    @pytest.mark.asyncio
    async def test_date_parsing(self):
        llm_response = json.dumps(
            {
                "source": "pypi",
                "fields": {"query": "fastapi"},
                "horizon": 30,
                "start": "2026-01-01",
                "end": "2026-06-30",
                "interpretation": "fastapi downloads this year",
            }
        )

        mock_client = MagicMock()
        mock_client.generate = AsyncMock(return_value=llm_response)

        result = await parse_and_resolve("fastapi this year", mock_client)

        assert isinstance(result, NaturalQueryResponse)
        assert result.start is not None
        assert str(result.start) == "2026-01-01"
        assert str(result.end) == "2026-06-30"
        assert result.horizon == 30


class TestHandleCompare:
    """Tests for _handle_compare helper."""

    @pytest.mark.asyncio
    async def test_valid_two_item_compare(self):
        parsed = {
            "compare": True,
            "items": [
                {
                    "source": "pypi",
                    "fields": {"query": "fastapi"},
                    "start": None,
                    "end": None,
                },
                {
                    "source": "pypi",
                    "fields": {"query": "django"},
                    "start": None,
                    "end": None,
                },
            ],
            "resample": None,
            "interpretation": "Comparing fastapi vs django",
        }
        result = await _handle_compare(parsed)
        assert isinstance(result, NaturalCompareResponse)
        assert len(result.items) == 2
        assert result.items[0].query == "fastapi"
        assert result.items[1].query == "django"
        assert result.interpretation == "Comparing fastapi vs django"

    @pytest.mark.asyncio
    async def test_valid_three_item_compare(self):
        parsed = {
            "compare": True,
            "items": [
                {
                    "source": "pypi",
                    "fields": {"query": "fastapi"},
                    "start": None,
                    "end": None,
                },
                {
                    "source": "pypi",
                    "fields": {"query": "django"},
                    "start": None,
                    "end": None,
                },
                {
                    "source": "pypi",
                    "fields": {"query": "flask"},
                    "start": None,
                    "end": None,
                },
            ],
            "resample": "week",
            "interpretation": "Comparing three frameworks",
        }
        result = await _handle_compare(parsed)
        assert isinstance(result, NaturalCompareResponse)
        assert len(result.items) == 3
        assert result.resample == "week"

    @pytest.mark.asyncio
    async def test_too_few_items(self):
        parsed = {
            "compare": True,
            "items": [
                {
                    "source": "pypi",
                    "fields": {"query": "fastapi"},
                    "start": None,
                    "end": None,
                }
            ],
            "interpretation": "Only one item",
        }
        result = await _handle_compare(parsed)
        assert isinstance(result, NaturalQueryError)
        assert "2-3 items" in result.error

    @pytest.mark.asyncio
    async def test_too_many_items(self):
        parsed = {
            "compare": True,
            "items": [
                {
                    "source": "pypi",
                    "fields": {"query": f"pkg{i}"},
                    "start": None,
                    "end": None,
                }
                for i in range(4)
            ],
            "interpretation": "Four items",
        }
        result = await _handle_compare(parsed)
        assert isinstance(result, NaturalQueryError)
        assert "2-3 items" in result.error

    @pytest.mark.asyncio
    async def test_unknown_source(self):
        parsed = {
            "compare": True,
            "items": [
                {
                    "source": "nonexistent",
                    "fields": {"query": "x"},
                    "start": None,
                    "end": None,
                },
                {
                    "source": "pypi",
                    "fields": {"query": "y"},
                    "start": None,
                    "end": None,
                },
            ],
            "interpretation": "test",
        }
        result = await _handle_compare(parsed)
        assert isinstance(result, NaturalQueryError)
        assert "Unknown data source" in result.error

    @pytest.mark.asyncio
    async def test_entity_resolution_in_compare(self):
        mock_adapter = MagicMock()
        mock_adapter.form_fields.return_value = [
            _field("league", "select"),
            _field("entity_type", "select"),
            _field("entity", "autocomplete", depends_on="league"),
            _field("metric", "select"),
            _field("home_away", "select"),
            _field("stage", "select"),
        ]
        mock_adapter.lookup = AsyncMock(return_value=MOCK_LOOKUP_ITEMS)

        parsed = {
            "compare": True,
            "items": [
                {
                    "source": "asa",
                    "fields": {
                        "league": "mls",
                        "entity_type": "teams",
                        "entity": "Seattle Sounders FC",
                        "metric": "xgoals_for",
                        "home_away": "all",
                        "stage": "all",
                    },
                    "start": None,
                    "end": None,
                },
                {
                    "source": "asa",
                    "fields": {
                        "league": "mls",
                        "entity_type": "teams",
                        "entity": "LA Galaxy",
                        "metric": "xgoals_for",
                        "home_away": "all",
                        "stage": "all",
                    },
                    "start": None,
                    "end": None,
                },
            ],
            "interpretation": "Comparing two MLS teams",
        }

        with patch("app.ai.query_parser.registry") as mock_registry:
            mock_registry.get.return_value = mock_adapter
            result = await _handle_compare(parsed)

        assert isinstance(result, NaturalCompareResponse)
        assert "jYQJ19EqGR" in result.items[0].query
        assert "kaDQ0wRqEv" in result.items[1].query

    @pytest.mark.asyncio
    async def test_date_parsing_in_compare(self):
        parsed = {
            "compare": True,
            "items": [
                {
                    "source": "pypi",
                    "fields": {"query": "fastapi"},
                    "start": "2026-01-01",
                    "end": None,
                },
                {
                    "source": "pypi",
                    "fields": {"query": "django"},
                    "start": "2026-01-01",
                    "end": None,
                },
            ],
            "interpretation": "test",
        }
        result = await _handle_compare(parsed)
        assert isinstance(result, NaturalCompareResponse)
        assert str(result.items[0].start) == "2026-01-01"
        assert result.items[0].end is None


class TestParseAndResolveCompare:
    """Tests for compare intent in parse_and_resolve."""

    @pytest.mark.asyncio
    async def test_compare_intent_dispatched(self):
        llm_response = json.dumps(
            {
                "compare": True,
                "items": [
                    {
                        "source": "pypi",
                        "fields": {"query": "fastapi"},
                        "start": None,
                        "end": None,
                    },
                    {
                        "source": "pypi",
                        "fields": {"query": "django"},
                        "start": None,
                        "end": None,
                    },
                ],
                "resample": None,
                "interpretation": "Comparing fastapi vs django downloads",
            }
        )

        mock_client = MagicMock()
        mock_client.generate = AsyncMock(return_value=llm_response)

        result = await parse_and_resolve("compare fastapi and django", mock_client)

        assert isinstance(result, NaturalCompareResponse)
        assert len(result.items) == 2
        assert result.items[0].source == "pypi"

    @pytest.mark.asyncio
    async def test_single_series_still_works(self):
        """Regression: single-series queries remain unaffected."""
        llm_response = json.dumps(
            {
                "source": "pypi",
                "fields": {"query": "fastapi"},
                "horizon": 14,
                "start": None,
                "end": None,
                "interpretation": "fastapi downloads",
            }
        )

        mock_client = MagicMock()
        mock_client.generate = AsyncMock(return_value=llm_response)

        result = await parse_and_resolve("fastapi downloads", mock_client)

        assert isinstance(result, NaturalQueryResponse)
        assert result.source == "pypi"

    @pytest.mark.asyncio
    async def test_single_query_with_resample_and_apply(self):
        """Single query can include resample and apply fields."""
        llm_response = json.dumps(
            {
                "source": "pypi",
                "fields": {"query": "fastapi"},
                "horizon": 14,
                "start": None,
                "end": None,
                "resample": "month",
                "apply": "rolling_avg_7d",
                "interpretation": "fastapi monthly downloads with rolling average",
            }
        )

        mock_client = MagicMock()
        mock_client.generate = AsyncMock(return_value=llm_response)

        result = await parse_and_resolve(
            "fastapi monthly downloads with rolling average", mock_client
        )

        assert isinstance(result, NaturalQueryResponse)
        assert result.source == "pypi"
        assert result.resample == "month"
        assert result.apply == "rolling_avg_7d"
