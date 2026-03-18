"""Tests for the plugin loading system."""

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from app.data.base import DataAdapter
from app.data.registry import AdapterRegistry
from app.models.plugin_schemas import PluginManifest
from app.plugins import (
    _load_plugin_file,
    load_plugins,
    reload_plugins,
    scan_plugins,
)

VALID_ADAPTER_CODE = """
import datetime
from app.data.base import DataAdapter
from app.models.schemas import DataPoint, TimeSeries

class TestAdapter(DataAdapter):
    name = "test_plugin"
    description = "Test plugin adapter"

    async def fetch(self, query, start=None, end=None):
        return TimeSeries(
            source=self.name,
            query=query,
            points=[DataPoint(date=datetime.date.today(), value=1.0)],
        )
"""


class TestLoadPluginFile:
    """Tests for _load_plugin_file function."""

    def test_load_valid_plugin(self, tmp_path: Path):
        """Should load a valid plugin file and return adapter."""
        plugin_file = tmp_path / "test_adapter.py"
        plugin_file.write_text(VALID_ADAPTER_CODE)

        adapter = _load_plugin_file(plugin_file)

        assert adapter is not None
        assert adapter.name == "test_plugin"
        assert adapter.description == "Test plugin adapter"
        assert isinstance(adapter, DataAdapter)

    def test_load_plugin_no_adapter(self, tmp_path: Path):
        """Should return None if plugin has no DataAdapter."""
        plugin_code = """
# Just some helper code, no adapter
def helper_function():
    return 42
"""
        plugin_file = tmp_path / "no_adapter.py"
        plugin_file.write_text(plugin_code)

        adapter = _load_plugin_file(plugin_file)

        assert adapter is None

    def test_load_plugin_missing_name(self, tmp_path: Path):
        """Should skip adapter class without name attribute."""
        plugin_code = """
import datetime
from app.data.base import DataAdapter
from app.models.schemas import TimeSeries

class IncompleteAdapter(DataAdapter):
    # Missing name and description
    async def fetch(self, query, start=None, end=None):
        return TimeSeries(source="x", query=query, points=[])
"""
        plugin_file = tmp_path / "incomplete.py"
        plugin_file.write_text(plugin_code)

        adapter = _load_plugin_file(plugin_file)

        assert adapter is None

    def test_load_plugin_syntax_error(self, tmp_path: Path):
        """Should raise exception on syntax error."""
        plugin_file = tmp_path / "bad_syntax.py"
        plugin_file.write_text("def broken(")

        with pytest.raises(SyntaxError):
            _load_plugin_file(plugin_file)


class TestLoadPlugins:
    """Tests for load_plugins function."""

    def test_no_plugins_dir(self, tmp_path: Path):
        """Should return 0 when plugins dir doesn't exist."""
        with patch("app.plugins.PLUGINS_DIR", tmp_path / "nonexistent"):
            count = load_plugins()
            assert count == 0

    def test_empty_plugins_dir(self, tmp_path: Path):
        """Should return 0 when plugins dir is empty."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        with patch("app.plugins.PLUGINS_DIR", plugins_dir):
            count = load_plugins()
            assert count == 0

    def test_skips_underscore_files(self, tmp_path: Path):
        """Should skip files starting with underscore."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        (plugins_dir / "_private.py").write_text("# private")

        with patch("app.plugins.PLUGINS_DIR", plugins_dir):
            count = load_plugins()
            assert count == 0

    def test_loads_valid_plugin(self, tmp_path: Path):
        """Should load and register valid plugin."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        plugin_code = """
import datetime
from app.data.base import DataAdapter
from app.models.schemas import DataPoint, TimeSeries

class PluginTestAdapter(DataAdapter):
    name = "plugin_test"
    description = "Test plugin"

    async def fetch(self, query, start=None, end=None):
        return TimeSeries(
            source=self.name,
            query=query,
            points=[
                DataPoint(
                    date=datetime.date.today(), value=1.0
                )
            ],
        )
"""
        (plugins_dir / "test_plugin.py").write_text(plugin_code)

        registered = []

        def mock_register(adapter, *, is_plugin=False):
            registered.append((adapter, is_plugin))

        with (
            patch("app.plugins.PLUGINS_DIR", plugins_dir),
            patch("app.plugins.registry.register", mock_register),
        ):
            count = load_plugins()

        assert count == 1
        assert len(registered) == 1
        assert registered[0][0].name == "plugin_test"
        assert registered[0][1] is True

    def test_loads_directory_plugin(self, tmp_path: Path):
        """Should load plugin from directory with manifest."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        plugin_dir = plugins_dir / "my_plugin"
        plugin_dir.mkdir()

        (plugin_dir / "plugin.json").write_text(
            json.dumps(
                {
                    "name": "my_plugin",
                    "description": "A dir plugin",
                    "author": "Test",
                    "version": "1.0.0",
                }
            )
        )
        (plugin_dir / "adapter.py").write_text(VALID_ADAPTER_CODE)

        registered = []

        def mock_register(adapter, *, is_plugin=False):
            registered.append((adapter, is_plugin))

        with (
            patch("app.plugins.PLUGINS_DIR", plugins_dir),
            patch("app.plugins.registry.register", mock_register),
        ):
            count = load_plugins()

        assert count == 1
        assert registered[0][0].name == "test_plugin"
        assert registered[0][1] is True

    def test_continues_on_error(self, tmp_path: Path):
        """Should continue loading if one plugin fails."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        (plugins_dir / "bad.py").write_text("def broken(")

        good_code = """
import datetime
from app.data.base import DataAdapter
from app.models.schemas import DataPoint, TimeSeries

class GoodAdapter(DataAdapter):
    name = "good_plugin"
    description = "Good plugin"

    async def fetch(self, query, start=None, end=None):
        return TimeSeries(
            source=self.name,
            query=query,
            points=[
                DataPoint(
                    date=datetime.date.today(), value=1.0
                )
            ],
        )
"""
        (plugins_dir / "good.py").write_text(good_code)

        registered = []

        def mock_register(adapter, *, is_plugin=False):
            registered.append((adapter, is_plugin))

        with (
            patch("app.plugins.PLUGINS_DIR", plugins_dir),
            patch("app.plugins.registry.register", mock_register),
        ):
            count = load_plugins()

        assert count == 1
        assert registered[0][0].name == "good_plugin"


class TestScanPlugins:
    """Tests for scan_plugins function."""

    def test_scan_no_dir(self, tmp_path: Path):
        """Should return empty list when no plugins dir."""
        with patch("app.plugins.PLUGINS_DIR", tmp_path / "nope"):
            result = scan_plugins()
            assert result == []

    def test_scan_flat_file(self, tmp_path: Path):
        """Flat .py file returns no_manifest status."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()
        (plugins_dir / "simple.py").write_text("# plugin")

        with patch("app.plugins.PLUGINS_DIR", plugins_dir):
            result = scan_plugins()

        assert len(result) == 1
        assert result[0].name == "simple"
        assert result[0].status == "no_manifest"

    def test_scan_directory_plugin_active(self, tmp_path: Path):
        """Directory plugin with valid manifest is active."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        pdir = plugins_dir / "cool_plugin"
        pdir.mkdir()
        (pdir / "plugin.json").write_text(
            json.dumps(
                {
                    "name": "cool_plugin",
                    "description": "Cool stuff",
                    "author": "Dev",
                    "version": "2.0.0",
                }
            )
        )
        (pdir / "adapter.py").write_text("# adapter code")

        with patch("app.plugins.PLUGINS_DIR", plugins_dir):
            result = scan_plugins()

        assert len(result) == 1
        info = result[0]
        assert info.name == "cool_plugin"
        assert info.status == "active"
        assert info.version == "2.0.0"
        assert info.author == "Dev"
        assert info.has_readme is False

    def test_scan_directory_with_readme(self, tmp_path: Path):
        """has_readme is True when README.md exists."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        pdir = plugins_dir / "readme_plugin"
        pdir.mkdir()
        (pdir / "plugin.json").write_text(
            json.dumps(
                {
                    "name": "readme_plugin",
                    "description": "Has docs",
                    "author": "Dev",
                    "version": "1.0.0",
                }
            )
        )
        (pdir / "adapter.py").write_text("# adapter")
        (pdir / "README.md").write_text("# Usage")

        with patch("app.plugins.PLUGINS_DIR", plugins_dir):
            result = scan_plugins()

        assert result[0].has_readme is True

    def test_scan_missing_env_vars(self, tmp_path: Path):
        """Missing required env vars yields missing_deps."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        pdir = plugins_dir / "env_plugin"
        pdir.mkdir()
        (pdir / "plugin.json").write_text(
            json.dumps(
                {
                    "name": "env_plugin",
                    "description": "Needs env",
                    "author": "Dev",
                    "version": "1.0.0",
                    "required_env_vars": ["SOME_UNLIKELY_VAR_XYZ"],
                }
            )
        )
        (pdir / "adapter.py").write_text("# adapter")

        with (
            patch("app.plugins.PLUGINS_DIR", plugins_dir),
            patch.dict(
                os.environ,
                {},
                clear=False,
            ),
        ):
            # Ensure the var is NOT set
            os.environ.pop("SOME_UNLIKELY_VAR_XYZ", None)
            result = scan_plugins()

        assert len(result) == 1
        assert result[0].status == "missing_deps"
        assert "SOME_UNLIKELY_VAR_XYZ" in (result[0].error_message or "")

    def test_scan_missing_adapter_py(self, tmp_path: Path):
        """Directory with manifest but no adapter.py is error."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        pdir = plugins_dir / "no_adapter"
        pdir.mkdir()
        (pdir / "plugin.json").write_text(
            json.dumps(
                {
                    "name": "no_adapter",
                    "description": "Missing adapter",
                    "author": "Dev",
                    "version": "1.0.0",
                }
            )
        )

        with patch("app.plugins.PLUGINS_DIR", plugins_dir):
            result = scan_plugins()

        assert len(result) == 1
        assert result[0].status == "error"
        assert "adapter.py" in (result[0].error_message or "")

    def test_scan_invalid_json(self, tmp_path: Path):
        """Invalid plugin.json yields error status."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        pdir = plugins_dir / "bad_json"
        pdir.mkdir()
        (pdir / "plugin.json").write_text("{invalid json!!")
        (pdir / "adapter.py").write_text("# adapter")

        with patch("app.plugins.PLUGINS_DIR", plugins_dir):
            result = scan_plugins()

        assert len(result) == 1
        assert result[0].status == "error"
        assert "Invalid plugin.json" in (result[0].error_message or "")

    def test_scan_missing_manifest_fields(self, tmp_path: Path):
        """Manifest missing required fields yields error."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        pdir = plugins_dir / "incomplete"
        pdir.mkdir()
        (pdir / "plugin.json").write_text(json.dumps({"name": "incomplete"}))
        (pdir / "adapter.py").write_text("# adapter")

        with patch("app.plugins.PLUGINS_DIR", plugins_dir):
            result = scan_plugins()

        assert len(result) == 1
        assert result[0].status == "error"
        assert "Invalid plugin.json" in (result[0].error_message or "")

    def test_scan_dir_without_manifest(self, tmp_path: Path):
        """Dir without plugin.json yields error status."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        pdir = plugins_dir / "bare_dir"
        pdir.mkdir()
        (pdir / "adapter.py").write_text("# adapter")

        with patch("app.plugins.PLUGINS_DIR", plugins_dir):
            result = scan_plugins()

        assert len(result) == 1
        assert result[0].status == "error"
        assert "plugin.json" in (result[0].error_message or "")


class TestManifestParsing:
    """Tests for PluginManifest model."""

    def test_valid_manifest(self):
        """Valid JSON parses to PluginManifest."""
        data = {
            "name": "test",
            "description": "desc",
            "author": "me",
            "version": "1.0.0",
            "required_env_vars": ["FOO", "BAR"],
        }
        m = PluginManifest(**data)
        assert m.name == "test"
        assert m.required_env_vars == ["FOO", "BAR"]

    def test_manifest_defaults(self):
        """required_env_vars defaults to empty list."""
        data = {
            "name": "test",
            "description": "desc",
            "author": "me",
            "version": "1.0.0",
        }
        m = PluginManifest(**data)
        assert m.required_env_vars == []

    def test_manifest_missing_required(self):
        """Missing required field raises ValueError."""
        with pytest.raises(Exception):
            PluginManifest(name="test")


class TestReloadPlugins:
    """Tests for reload_plugins function."""

    def test_reload_unregisters_and_reloads(self, tmp_path: Path):
        """reload_plugins unregisters old and re-loads."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        (plugins_dir / "simple.py").write_text(VALID_ADAPTER_CODE)

        mock_registry = AdapterRegistry()
        # Pre-register a fake plugin adapter
        mock_registry.plugin_adapters.add("old_plugin")

        registered = []
        original_register = mock_registry.register

        def tracking_register(adapter, *, is_plugin=False):
            original_register(adapter, is_plugin=is_plugin)
            registered.append(adapter.name)

        with (
            patch("app.plugins.PLUGINS_DIR", plugins_dir),
            patch("app.plugins.registry", mock_registry),
            patch.object(mock_registry, "register", tracking_register),
        ):
            result = reload_plugins()

        # Old plugin was unregistered
        assert "old_plugin" not in mock_registry.plugin_adapters
        # New plugin was loaded
        assert len(registered) == 1
        assert registered[0] == "test_plugin"
        # Returns scan results
        assert isinstance(result, list)


class TestUnregister:
    """Tests for AdapterRegistry.unregister."""

    def test_unregister_removes_adapter(self):
        """unregister removes adapter from registry."""
        reg = AdapterRegistry()

        class FakeAdapter:
            name = "fake"
            description = "fake"

        reg._adapters["fake"] = FakeAdapter()
        reg.plugin_adapters.add("fake")

        reg.unregister("fake")

        assert "fake" not in reg._adapters
        assert "fake" not in reg.plugin_adapters

    def test_unregister_nonexistent_is_noop(self):
        """unregister of nonexistent name doesn't raise."""
        reg = AdapterRegistry()
        reg.unregister("nonexistent")  # should not raise
