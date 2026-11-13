"""Closed journal event catalogue."""

from app.contracts.enums import EventType

EVENT_CATALOG: frozenset[EventType] = frozenset(EventType)
