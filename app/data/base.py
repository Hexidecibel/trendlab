import datetime
from abc import ABC, abstractmethod

from app.models.schemas import FormField, LookupItem, TimeSeries


class DataAdapter(ABC):
    name: str
    description: str

    @abstractmethod
    async def fetch(
        self,
        query: str,
        start: datetime.date | None = None,
        end: datetime.date | None = None,
    ) -> TimeSeries: ...

    def form_fields(self) -> list[FormField]:
        """Return form field definitions for this adapter's query UI.

        Override to provide adapter-specific fields (dropdowns, autocomplete).
        Default returns a single text field.
        """
        return [
            FormField(
                name="query",
                label="Query",
                field_type="text",
                placeholder="Enter query...",
            )
        ]

    async def lookup(self, lookup_type: str, **kwargs: str) -> list[LookupItem]:
        """Return lookup items for autocomplete fields.

        Override to provide dynamic options (e.g. team lists, player lists).
        """
        return []
