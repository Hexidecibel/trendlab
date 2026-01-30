import pytest

from app.data.adapters.pypi import PyPIAdapter
from app.data.registry import AdapterRegistry


@pytest.fixture
def registry():
    return AdapterRegistry()


class TestAdapterRegistry:
    def test_register_and_get(self, registry):
        adapter = PyPIAdapter()
        registry.register(adapter)
        assert registry.get("pypi") is adapter

    def test_get_unknown_raises_key_error(self, registry):
        with pytest.raises(KeyError):
            registry.get("nonexistent")

    def test_list_sources_empty(self, registry):
        assert registry.list_sources() == []

    def test_list_sources_after_register(self, registry):
        adapter = PyPIAdapter()
        registry.register(adapter)
        sources = registry.list_sources()
        assert len(sources) == 1
        assert sources[0].name == "pypi"
        assert "PyPI" in sources[0].description
