from app.data.base import DataAdapter
from app.models.schemas import DataSourceInfo


class AdapterRegistry:
    def __init__(self):
        self._adapters: dict[str, DataAdapter] = {}

    def register(self, adapter: DataAdapter) -> None:
        self._adapters[adapter.name] = adapter

    def get(self, name: str) -> DataAdapter:
        return self._adapters[name]

    def list_sources(self) -> list[DataSourceInfo]:
        return [
            DataSourceInfo(name=a.name, description=a.description)
            for a in self._adapters.values()
        ]


registry = AdapterRegistry()
