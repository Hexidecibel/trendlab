"""Natural language query parser — converts free-form text to structured params."""

import datetime
import json
import logging

from app.ai.client import LLMClient
from app.config import settings
from app.data.registry import registry
from app.models.schemas import (
    LookupItem,
    NaturalCompareItem,
    NaturalCompareResponse,
    NaturalQueryError,
    NaturalQueryResponse,
)

logger = logging.getLogger(__name__)


def _get_client(client: LLMClient | None) -> LLMClient:
    """Return the provided client or create one from settings."""
    if client is not None:
        return client
    if not settings.anthropic_api_key:
        raise ValueError("ANTHROPIC_API_KEY not configured")
    return LLMClient(api_key=settings.anthropic_api_key)


# ---------------------------------------------------------------------------
# Catalog prompt builder
# ---------------------------------------------------------------------------


def build_catalog_prompt() -> str:
    """Build a text description of all available adapters for the LLM."""
    sources = registry.list_sources()
    lines = ["Available data sources:", ""]
    for src in sources:
        lines.append(f"## {src.name}")
        lines.append(f"Description: {src.description}")
        if src.form_fields:
            lines.append("Fields:")
            for field in src.form_fields:
                desc = f"  - {field.name} ({field.field_type})"
                if field.options:
                    vals = [f"{o.value} ({o.label})" for o in field.options]
                    desc += f": valid values = [{', '.join(vals)}]"
                if field.placeholder:
                    desc += f" (example: {field.placeholder})"
                if field.depends_on:
                    desc += f" [depends on: {field.depends_on}]"
                lines.append(desc)
        # Document query format
        if len(src.form_fields) == 1 and src.form_fields[0].name == "query":
            lines.append(
                f"Query format: plain text (e.g., '{src.form_fields[0].placeholder}')"
            )
        elif len(src.form_fields) > 1:
            names = ":".join(f.name for f in src.form_fields)
            lines.append(f"Query format: colon-separated = {names}")
        lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Fuzzy matching
# ---------------------------------------------------------------------------


def _find_best_match(query: str, items: list[LookupItem]) -> LookupItem | None:
    """Find the best matching lookup item for a human-readable name.

    Matching priority:
    1. Exact match (case-insensitive)
    2. Substring containment
    3. Token overlap (Jaccard similarity >= 0.3)
    """
    query_lower = query.lower().strip()
    if not query_lower or not items:
        return None

    # 1. Exact match
    for item in items:
        if item.label.lower().strip() == query_lower:
            return item

    # 2. Substring containment
    for item in items:
        label_lower = item.label.lower()
        if query_lower in label_lower or label_lower in query_lower:
            return item

    # 3. Token overlap (Jaccard)
    query_tokens = set(query_lower.split())
    best_score = 0.0
    best_item = None
    for item in items:
        item_tokens = set(item.label.lower().split())
        intersection = query_tokens & item_tokens
        union = query_tokens | item_tokens
        score = len(intersection) / len(union) if union else 0
        if score > best_score and score >= 0.3:
            best_score = score
            best_item = item

    return best_item


# ---------------------------------------------------------------------------
# Query string builder
# ---------------------------------------------------------------------------


def build_query_string(source_name: str, resolved_fields: dict[str, str]) -> str:
    """Build the final colon-separated query string from resolved fields.

    Mirrors the frontend buildQuery() logic in QueryForm.tsx.
    """
    adapter = registry.get(source_name)
    form_fields = adapter.form_fields()

    # Simple adapters: single "query" field
    if len(form_fields) == 1 and form_fields[0].name == "query":
        return resolved_fields.get("query", "")

    # Complex adapters: join in form_fields order
    parts = []
    for ff in form_fields:
        parts.append(resolved_fields.get(ff.name, ""))
    return ":".join(parts)


# ---------------------------------------------------------------------------
# Entity resolution
# ---------------------------------------------------------------------------


async def resolve_entities(
    source_name: str,
    fields: dict[str, str],
) -> dict[str, str]:
    """Resolve human-readable entity names to internal IDs.

    For autocomplete fields, fetches lookup data and fuzzy-matches.
    """
    adapter = registry.get(source_name)
    form_fields = adapter.form_fields()
    resolved = dict(fields)

    for ff in form_fields:
        if ff.field_type != "autocomplete":
            continue
        if ff.name not in fields:
            continue

        human_name = fields[ff.name]

        # Build lookup kwargs from depends_on
        kwargs: dict[str, str] = {}
        if ff.depends_on and ff.depends_on in fields:
            kwargs[ff.depends_on] = fields[ff.depends_on]

        # Map field name to lookup type
        lookup_type = "teams" if ff.name == "entity" else ff.name

        lookup_items = await adapter.lookup(lookup_type, **kwargs)

        match = _find_best_match(human_name, lookup_items)
        if match:
            resolved[ff.name] = match.value
        else:
            available = ", ".join(item.label for item in lookup_items[:10])
            raise ValueError(
                f"Could not resolve '{human_name}'. Available: {available}"
            )

    return resolved


# ---------------------------------------------------------------------------
# JSON extraction
# ---------------------------------------------------------------------------


def _extract_json(raw: str) -> dict:
    """Extract JSON from LLM response, handling markdown fences."""
    text = raw.strip()
    # Strip markdown code fences
    if text.startswith("```"):
        # Remove opening fence line
        first_newline = text.find("\n")
        if first_newline != -1:
            text = text[first_newline + 1 :]
        else:
            text = text[3:]
        # Remove closing fence
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
    return json.loads(text)


# ---------------------------------------------------------------------------
# LLM prompt templates
# ---------------------------------------------------------------------------

SYSTEM_PROMPT_TEMPLATE = """\
You are a query parser for TrendLab, a trend analysis platform.
Your job is to parse natural language queries into structured parameters.

RULES:
1. Always respond with valid JSON only. No markdown fences, no explanation text.
2. Match the user's intent to exactly ONE data source from the catalog below.
3. For entity names (teams, etc.), use the HUMAN-READABLE name, not the ID.
4. Default horizon to 14 if not mentioned.
5. Default optional fields (home_away, stage) to "all" if not mentioned.
6. If the query is ambiguous or doesn't match any source, return an error response.
7. For date ranges, interpret relative terms using today's date ({today}):
   - "this season" / "this year" → start = {year}-01-01
   - "last 30 days" → start = appropriate date
   - If no date mentioned, set start and end to null.
8. COMPARE INTENT: If the user wants to compare multiple items (keywords: "compare",
   "vs", "versus", "and" between two entities, "side by side"), return a compare
   response with 2-3 items instead of a single query. Max 3 items.
9. RESAMPLE / TRANSFORM: If the user mentions aggregation (weekly, monthly,
   quarterly, seasonal), set "resample" to "week", "month", "quarter", or "season".
   If they mention transforms (normalize, rolling average, percentage change),
   set "apply" to a pipe-delimited string (e.g. "rolling_avg_7d|normalize").
   Default both to null.

{catalog}

EXAMPLES:

Query: "Show me fastapi download trends"
Response: {{"source": "pypi", "fields": {{"query": "fastapi"}}, "horizon": 14, \
"start": null, "end": null, "resample": null, "apply": null, \
"interpretation": "PyPI download counts for the fastapi package"}}

Query: "Seattle Sounders expected goals at home this season"
Response: {{"source": "asa", "fields": {{"league": "mls", "entity_type": "teams", \
"entity": "Seattle Sounders FC", "metric": "xgoals_for", "home_away": "home", \
"stage": "regular"}}, "horizon": 14, "start": "{year}-01-01", "end": null, \
"resample": null, "apply": null, \
"interpretation": "Expected goals (xG) for Seattle Sounders FC in home MLS \
regular season games this season"}}

Query: "bitcoin price forecast for the next month"
Response: {{"source": "crypto", "fields": {{"query": "bitcoin"}}, "horizon": 30, \
"start": null, "end": null, "resample": null, "apply": null, \
"interpretation": "Bitcoin cryptocurrency price with a 30-day forecast horizon"}}

Query: "fastapi monthly downloads with rolling average"
Response: {{"source": "pypi", "fields": {{"query": "fastapi"}}, "horizon": 14, \
"start": null, "end": null, "resample": "month", "apply": "rolling_avg_7d", \
"interpretation": "PyPI downloads for fastapi aggregated monthly with rolling average"}}

Query: "How's the weather in Seattle?"
Response: {{"error": "This query doesn't match any available data source. \
TrendLab tracks software packages, cryptocurrencies, and soccer metrics.", \
"suggestions": ["Try 'Bitcoin price trend'", "Try 'fastapi download counts'", \
"Try 'Seattle Sounders expected goals'"]}}

Query: "compare fastapi and django downloads"
Response: {{"compare": true, "items": [\
{{"source": "pypi", "fields": {{"query": "fastapi"}}, "start": null, "end": null}}, \
{{"source": "pypi", "fields": {{"query": "django"}}, "start": null, "end": null}}], \
"resample": null, \
"interpretation": "Comparing PyPI download counts for fastapi vs django"}}

Query: "Seattle Sounders vs LA Galaxy xG this season"
Response: {{"compare": true, "items": [\
{{"source": "asa", "fields": {{"league": "mls", "entity_type": "teams", \
"entity": "Seattle Sounders FC", "metric": "xgoals_for", "home_away": "all", \
"stage": "regular"}}, "start": "{year}-01-01", "end": null}}, \
{{"source": "asa", "fields": {{"league": "mls", "entity_type": "teams", \
"entity": "LA Galaxy", "metric": "xgoals_for", "home_away": "all", \
"stage": "regular"}}, "start": "{year}-01-01", "end": null}}], \
"resample": null, \
"interpretation": "Comparing expected goals for Seattle Sounders FC vs LA Galaxy \
in MLS regular season this season"}}"""

USER_PROMPT_TEMPLATE = """\
Parse this natural language query into structured parameters.
Return ONLY valid JSON, no markdown fences, no explanation.

Query: {text}

Respond with JSON:
{{"source": "<source_name>", "fields": {{<field_name>: <value>, ...}}, \
"horizon": <integer>, "start": "<YYYY-MM-DD or null>", \
"end": "<YYYY-MM-DD or null>", \
"resample": "<week|month|quarter|season or null>", \
"apply": "<pipe-delimited transforms or null>", \
"interpretation": "<one sentence explaining what you understood>"}}

If the user wants to COMPARE multiple items, respond with:
{{"compare": true, "items": [\
{{"source": "<source>", "fields": {{...}}, "start": "<YYYY-MM-DD or null>", \
"end": "<YYYY-MM-DD or null>"}}, ...], \
"resample": "<frequency or null>", \
"interpretation": "<one sentence>"}}

If you cannot parse the query, respond with:
{{"error": "<explanation>", "suggestions": ["<suggestion1>", "<suggestion2>"]}}"""


# ---------------------------------------------------------------------------
# Date parsing helper
# ---------------------------------------------------------------------------


def _parse_date(value: str | None) -> datetime.date | None:
    """Parse a date string, returning None for null/empty/invalid."""
    if not value or value == "null":
        return None
    try:
        return datetime.date.fromisoformat(value)
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------


async def _handle_compare(
    parsed: dict,
) -> NaturalCompareResponse | NaturalQueryError:
    """Handle compare-intent responses from the LLM."""
    items_raw = parsed.get("items", [])
    if len(items_raw) < 2 or len(items_raw) > 3:
        return NaturalQueryError(
            error="Compare requires 2-3 items",
            suggestions=["Try 'compare X and Y'"],
        )

    resolved_items: list[NaturalCompareItem] = []
    for item_data in items_raw:
        source = item_data.get("source", "")
        try:
            registry.get(source)
        except KeyError:
            available = ", ".join(s.name for s in registry.list_sources())
            return NaturalQueryError(
                error=f"Unknown data source: '{source}'",
                suggestions=[f"Available sources: {available}"],
            )

        fields = item_data.get("fields", {})
        try:
            resolved = await resolve_entities(source, fields)
        except ValueError as e:
            return NaturalQueryError(error=str(e))

        query_string = build_query_string(source, resolved)
        start = _parse_date(item_data.get("start"))
        end = _parse_date(item_data.get("end"))

        resolved_items.append(
            NaturalCompareItem(source=source, query=query_string, start=start, end=end)
        )

    return NaturalCompareResponse(
        items=resolved_items,
        resample=parsed.get("resample"),
        interpretation=parsed.get("interpretation", ""),
    )


async def parse_and_resolve(
    text: str,
    client: LLMClient | None = None,
) -> NaturalQueryResponse | NaturalCompareResponse | NaturalQueryError:
    """Full pipeline: parse natural language, resolve entities, build query."""
    llm = _get_client(client)

    # 1. Build prompt with adapter catalog
    catalog = build_catalog_prompt()
    today = datetime.date.today()
    system_msg = SYSTEM_PROMPT_TEMPLATE.format(
        catalog=catalog,
        today=today.isoformat(),
        year=today.year,
    )
    user_msg = USER_PROMPT_TEMPLATE.format(text=text)
    messages = [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": user_msg},
    ]

    # 2. Call LLM
    raw = await llm.generate(messages, max_tokens=512)

    # 3. Parse JSON
    try:
        parsed = _extract_json(raw)
    except (json.JSONDecodeError, ValueError):
        return NaturalQueryError(
            error="Failed to parse response",
            suggestions=["Try rephrasing your query more specifically"],
        )

    # 4. Check for compare intent
    if parsed.get("compare"):
        return await _handle_compare(parsed)

    # 5. Check for LLM-reported error
    if "error" in parsed:
        return NaturalQueryError(
            error=parsed["error"],
            suggestions=parsed.get("suggestions", []),
        )

    # 6. Validate source exists
    source = parsed.get("source", "")
    try:
        registry.get(source)
    except KeyError:
        available = ", ".join(s.name for s in registry.list_sources())
        return NaturalQueryError(
            error=f"Unknown data source: '{source}'",
            suggestions=[f"Available sources: {available}"],
        )

    # 7. Resolve entities (autocomplete fields)
    fields = parsed.get("fields", {})
    try:
        resolved = await resolve_entities(source, fields)
    except ValueError as e:
        return NaturalQueryError(error=str(e))

    # 8. Build final query string
    query_string = build_query_string(source, resolved)

    # 9. Parse dates
    start = _parse_date(parsed.get("start"))
    end = _parse_date(parsed.get("end"))

    return NaturalQueryResponse(
        source=source,
        query=query_string,
        horizon=parsed.get("horizon", 14),
        start=start,
        end=end,
        resample=parsed.get("resample"),
        apply=parsed.get("apply"),
        interpretation=parsed.get("interpretation", ""),
    )
