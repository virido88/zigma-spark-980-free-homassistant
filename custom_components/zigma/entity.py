"""Shared base entity for Zigma entities."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ZigmaCoordinator, ZigmaScheduleCoordinator


class ZigmaEntity(CoordinatorEntity[ZigmaCoordinator]):
    """One device per config entry."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: ZigmaCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        robot = (coordinator.data or {}).get("robot") or entry.title
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer="Zigma",
            name=f"Zigma {robot}",
        )


class ZigmaScheduleEntity(CoordinatorEntity[ZigmaScheduleCoordinator]):
    """Base for entities that represent one robot schedule."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: ZigmaScheduleCoordinator, entry: ConfigEntry, schedule_id: int
    ) -> None:
        super().__init__(coordinator)
        self._schedule_id = schedule_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer="Zigma",
            name=entry.title,
        )

    @property
    def schedule(self) -> dict | None:
        """Return the current schedule dict, or None if it was deleted."""
        return next(
            (i for i in (self.coordinator.data or []) if i.get("id") == self._schedule_id),
            None,
        )

    @property
    def available(self) -> bool:
        """Unavailable if the schedule disappeared."""
        return super().available and self.schedule is not None
