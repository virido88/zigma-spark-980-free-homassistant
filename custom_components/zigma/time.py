"""Time entity per robot schedule: change its start time."""

from __future__ import annotations

from datetime import time

from homeassistant.components.time import TimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import ZigmaScheduleCoordinator
from .entity import ZigmaScheduleEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create a time entity for every schedule, including ones added later."""
    coordinator: ZigmaScheduleCoordinator = hass.data[DOMAIN][f"{entry.entry_id}_schedules"]
    known: set[int] = set()

    @callback
    def _async_add_new() -> None:
        new = []
        for item in coordinator.data or []:
            sid = item.get("id")
            if sid is None or sid in known:
                continue
            known.add(sid)
            new.append(ZigmaScheduleTime(coordinator, entry, sid))
        if new:
            async_add_entities(new)

    _async_add_new()
    entry.async_on_unload(coordinator.async_add_listener(_async_add_new))


class ZigmaScheduleTime(ZigmaScheduleEntity, TimeEntity):
    """Start time of one schedule."""

    def __init__(
        self, coordinator: ZigmaScheduleCoordinator, entry: ConfigEntry, schedule_id: int
    ) -> None:
        super().__init__(coordinator, entry, schedule_id)
        self._attr_unique_id = f"{entry.entry_id}_schedule_{schedule_id}_time"

    @property
    def name(self) -> str | None:
        """Label the entity so it is clear which schedule it belongs to."""
        label = self.schedule.get("label") if self.schedule else None
        return f"{label} Uhrzeit" if label else None

    @property
    def native_value(self) -> time | None:
        """Return the schedule's start time."""
        if not self.schedule:
            return None
        try:
            return time.fromisoformat(self.schedule["time"])
        except (KeyError, TypeError, ValueError):
            return None

    async def async_set_value(self, value: time) -> None:
        """Change the start time (robot stores it as HH:MM)."""
        await self.coordinator.async_update_schedule(
            self._schedule_id, {"time": value.strftime("%H:%M")}
        )
