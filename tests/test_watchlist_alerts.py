"""Tests for watchlist trend alerts (trend flip, slope crossing), the
additive column migration and the watchlist API."""

import datetime
import math

import pytest
from sqlalchemy import create_engine, inspect, text

import app.db.engine as db_engine
from app.db import repository as repo
from app.models.schemas import DataPoint, TimeSeries, WatchlistItemResponse
from app.services import watchlist_checker
from app.services.watchlist_checker import check_watchlist, evaluate_alert

BASE = datetime.date(2024, 1, 1)


@pytest.fixture
async def db():
    await db_engine.init_db("sqlite+aiosqlite://")
    yield


def _item(**kw) -> WatchlistItemResponse:
    d = dict(
        id=1,
        name="w",
        source="test",
        query="q",
        created_at=datetime.datetime.now(datetime.UTC),
    )
    d.update(kw)
    return WatchlistItemResponse(**d)


def _series(values: list[float]) -> TimeSeries:
    return TimeSeries(
        source="test",
        query="q",
        points=[
            DataPoint(date=BASE + datetime.timedelta(days=i), value=v)
            for i, v in enumerate(values)
        ],
    )


def rising(n=120, rate=0.01):
    return _series([1000.0 * math.exp(rate * i) for i in range(n)])


def falling(n=120, rate=0.01):
    return _series([1000.0 * math.exp(-rate * i) for i in range(n)])


class TestEvaluateAlert:
    def test_trend_flip_needs_a_baseline(self):
        fired, msg = evaluate_alert(_item(alert_type="trend_flip"), 1.0, "rising", 5.0)
        assert not fired and msg is None

    def test_trend_flip_same_direction_is_quiet(self):
        item = _item(alert_type="trend_flip", last_direction="rising")
        assert evaluate_alert(item, 1.0, "rising", 5.0) == (False, None)

    def test_trend_flip_fires_on_change(self):
        item = _item(alert_type="trend_flip", last_direction="rising")
        fired, msg = evaluate_alert(item, 1.0, "falling", -4.0)
        assert fired
        assert msg == "trend flipped from rising to falling"

    def test_trend_flip_to_stable_counts(self):
        item = _item(alert_type="trend_flip", last_direction="falling")
        fired, _ = evaluate_alert(item, 1.0, "stable", 0.5)
        assert fired

    def test_slope_crossing_up(self):
        item = _item(alert_type="slope", slope_threshold=5.0, last_slope=2.0)
        fired, msg = evaluate_alert(item, 1.0, "rising", 7.25)
        assert fired
        assert "rose above +5%/mo" in msg and "+7.2%/mo" in msg

    def test_slope_crossing_down(self):
        item = _item(alert_type="slope", slope_threshold=5.0, last_slope=8.0)
        fired, msg = evaluate_alert(item, 1.0, "rising", 3.0)
        assert fired
        assert "fell below +5%/mo" in msg

    def test_slope_negative_threshold(self):
        item = _item(alert_type="slope", slope_threshold=-10.0, last_slope=-4.0)
        fired, msg = evaluate_alert(item, 1.0, "falling", -12.0)
        assert fired and "fell below -10%/mo" in msg

    def test_slope_staying_above_is_quiet(self):
        item = _item(alert_type="slope", slope_threshold=5.0, last_slope=6.0)
        assert evaluate_alert(item, 1.0, "rising", 9.0) == (False, None)

    def test_slope_first_check_is_baseline(self):
        item = _item(alert_type="slope", slope_threshold=5.0)
        assert evaluate_alert(item, 1.0, "rising", 9.0) == (False, None)

    def test_threshold_still_works(self):
        item = _item(threshold_direction="above", threshold_value=100.0)
        fired, msg = evaluate_alert(item, 45_000_000.0, None, None)
        assert fired and msg == "45.0M is above 100"
        assert evaluate_alert(item, 50.0, None, None) == (False, None)

    def test_no_alert(self):
        assert evaluate_alert(_item(), 1e9, "rising", 50.0) == (False, None)


class _FakeCache:
    def __init__(self, ts):
        self.ts = ts

    async def fetch(self, adapter, query):
        return self.ts


class TestCheckWatchlistTrendAlerts:
    @pytest.fixture(autouse=True)
    def _adapter(self, monkeypatch):
        class _A:
            aggregation_method = "mean"

        monkeypatch.setattr(watchlist_checker.registry, "get", lambda name: _A())

    @pytest.mark.asyncio
    async def test_trend_flip_between_checks(self, db):
        await repo.add_watchlist_item(
            name="flip", source="test", query="q", alert_type="trend_flip"
        )
        first = await check_watchlist(cache=_FakeCache(rising()))
        assert first.alerts == []
        assert first.items[0].last_direction == "rising"
        assert first.items[0].last_slope is not None and first.items[0].last_slope > 0

        again = await check_watchlist(cache=_FakeCache(rising()))
        assert again.alerts == []

        flipped = await check_watchlist(cache=_FakeCache(falling()))
        assert len(flipped.alerts) == 1
        alert = flipped.alerts[0]
        assert alert.triggered
        assert alert.alert_message == "trend flipped from rising to falling"
        stored = await repo.get_watchlist_item(alert.id)
        assert stored.last_direction == "falling"

    @pytest.mark.asyncio
    async def test_slope_crosses_threshold(self, db):
        await repo.add_watchlist_item(
            name="slope",
            source="test",
            query="q",
            alert_type="slope",
            slope_threshold=20.0,
        )
        # ~+3%/month, then ~+35%/month
        slow = await check_watchlist(cache=_FakeCache(rising(rate=0.001)))
        assert slow.alerts == []
        assert slow.items[0].last_slope < 20.0
        fast = await check_watchlist(cache=_FakeCache(rising(rate=0.01)))
        assert len(fast.alerts) == 1
        assert "rose above +20%/mo" in fast.alerts[0].alert_message


class TestAdditiveMigration:
    @pytest.mark.asyncio
    async def test_old_watchlist_table_gains_new_columns(self, tmp_path):
        path = tmp_path / "old.db"
        eng = create_engine(f"sqlite:///{path}")
        with eng.begin() as conn:
            conn.execute(
                text(
                    "CREATE TABLE watchlist_items ("
                    "id INTEGER PRIMARY KEY, name VARCHAR NOT NULL, "
                    "source VARCHAR NOT NULL, query VARCHAR NOT NULL, "
                    "resample VARCHAR, threshold_direction VARCHAR, "
                    "threshold_value INTEGER, last_value INTEGER, "
                    "last_checked_at DATETIME, created_at DATETIME NOT NULL, "
                    "CONSTRAINT uq_watchlist_source_query UNIQUE (source, query))"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO watchlist_items (name, source, query, "
                    "threshold_direction, threshold_value, created_at) VALUES "
                    "('old', 'pypi', 'requests', 'above', 100, '2024-01-01 00:00:00')"
                )
            )
        eng.dispose()

        await db_engine.init_db(f"sqlite+aiosqlite:///{path}")

        eng = create_engine(f"sqlite:///{path}")
        cols = {c["name"] for c in inspect(eng).get_columns("watchlist_items")}
        eng.dispose()
        for c in ("alert_type", "slope_threshold", "last_direction", "last_slope"):
            assert c in cols

        items = await repo.list_watchlist()
        assert len(items) == 1
        # Legacy threshold rows read back as threshold alerts
        assert items[0].alert_type == "threshold"
        assert items[0].threshold_value == 100.0

        updated = await repo.update_watchlist_item(
            items[0].id, last_direction="rising", last_slope=3.5, last_value=0.35
        )
        assert updated.last_direction == "rising"
        assert updated.last_slope == 3.5
        assert updated.last_value == 0.35  # floats are no longer truncated

        # Idempotent
        await db_engine.init_db(f"sqlite+aiosqlite:///{path}")
        await db_engine.init_db("sqlite+aiosqlite://")


class TestWatchlistApi:
    @pytest.mark.asyncio
    async def test_add_trend_flip_and_duplicate(self, client, db):
        body = {
            "name": "requests",
            "source": "pypi",
            "query": "requests",
            "resample": "week",
            "alert_type": "trend_flip",
        }
        r = await client.post("/api/watchlist", json=body)
        assert r.status_code == 200
        item = r.json()
        assert item["alert_type"] == "trend_flip"
        assert item["resample"] == "week"

        dup = await client.post("/api/watchlist", json=body)
        assert dup.status_code == 409
        assert dup.json()["existing"]["id"] == item["id"]

    @pytest.mark.asyncio
    async def test_slope_alert_needs_threshold(self, client, db):
        r = await client.post(
            "/api/watchlist",
            json={"name": "x", "source": "pypi", "query": "x", "alert_type": "slope"},
        )
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_patch_changes_alert(self, client, db):
        r = await client.post(
            "/api/watchlist",
            json={
                "name": "x",
                "source": "pypi",
                "query": "x",
                "alert_type": "trend_flip",
            },
        )
        item_id = r.json()["id"]
        r = await client.patch(
            f"/api/watchlist/{item_id}",
            json={"alert_type": "slope", "slope_threshold": 5},
        )
        assert r.status_code == 200
        assert r.json()["alert_type"] == "slope"
        assert r.json()["slope_threshold"] == 5.0

        r = await client.patch(f"/api/watchlist/{item_id}", json={"alert_type": None})
        assert r.status_code == 200
        assert r.json()["alert_type"] is None

        r = await client.patch(
            f"/api/watchlist/{item_id}", json={"alert_type": "threshold"}
        )
        assert r.status_code == 422
        assert (await client.patch("/api/watchlist/9999", json={})).status_code == 404
