"""Switch per robot schedule: enable or disable it."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
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
    """Create a switch for every schedule, including ones added later."""
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
            new.append(ZigmaScheduleSwitch(coordinator, entry, sid))
        if new:
            async_add_entities(new)

    _async_add_new()
    entry.async_on_unload(coordinator.async_add_listener(_async_add_new))


class ZigmaScheduleSwitch(ZigmaScheduleEntity, SwitchEntity):
    """Enabled state of one schedule."""

    def __init__(
        self, coordinator: ZigmaScheduleCoordinator, entry: ConfigEntry, schedule_id: int
    ) -> None:
        super().__init__(coordinator, entry, schedule_id)
        self._attr_unique_id = f"{entry.entry_id}_schedule_{schedule_id}_enabled"

    @property
    def name(self) -> str | None:
        """Use the schedule label as name."""
        return self.schedule.get("label") if self.schedule else None

    @property
    def is_on(self) -> bool:
        """True if the schedule is enabled."""
        return bool(self.schedule and self.schedule.get("enabled"))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the schedule's action and weekdays for reference."""
        s = self.schedule or {}
        return {
            "action": s.get("action"),
            "time": s.get("time"),
            "days": s.get("days"),
            "fan_power": s.get("fan_power"),
            "last_result": s.get("last_result"),
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the schedule."""
        await self.coordinator.async_update_schedule(self._schedule_id, {"enabled": True})

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the schedule."""
        await self.coordinator.async_update_schedule(self._schedule_id, {"enabled": False})
