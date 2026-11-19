"""Vacuum entity: start, pause, return to dock, fan power."""

from __future__ import annotations

from typing import Any

from homeassistant.components.vacuum import (
    StateVacuumEntity,
    VacuumActivity,
    VacuumEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import ZigmaError
from .const import DEFAULT_FAN_POWER, DOMAIN, FAN_POWERS
from .coordinator import ZigmaCoordinator
from .entity import ZigmaEntity

CLEANING_STATES = {"AutoClean", "PlanningRect", "SpotClean", "SelectClean", "cleaning"}
DOCKED_STATES = {"charging", "PileCharging", "DirCharging"}
PAUSED_STATES = {"Pause", "paused"}
RETURNING_STATES = {"BackCharging", "returning"}
IDLE_STATES = {"Standby", "idle"}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the vacuum entity."""
    coordinator: ZigmaCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ZigmaVacuum(coordinator, entry)])


class ZigmaVacuum(ZigmaEntity, StateVacuumEntity):
    """The robot as a Home Assistant vacuum."""

    _attr_name = None
    _attr_supported_features = (
        VacuumEntityFeature.START
        | VacuumEntityFeature.PAUSE
        | VacuumEntityFeature.RETURN_HOME
        | VacuumEntityFeature.FAN_SPEED
    )
    _attr_fan_speed_list = list(FAN_POWERS)

    def __init__(self, coordinator: ZigmaCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_vacuum"
        self._fan_speed = DEFAULT_FAN_POWER

    @property
    def _status(self) -> str:
        return str((self.coordinator.data or {}).get("working_status", "unknown"))

    @property
    def activity(self) -> VacuumActivity | None:
        """Map the robot's working status to a vacuum activity."""
        data = self.coordinator.data or {}
        if data.get("error") not in (None, "NoError"):
            return VacuumActivity.ERROR
        status = self._status
        if status in CLEANING_STATES:
            return VacuumActivity.CLEANING
        if status in DOCKED_STATES:
            return VacuumActivity.DOCKED
        if status in PAUSED_STATES:
            return VacuumActivity.PAUSED
        if status in RETURNING_STATES:
            return VacuumActivity.RETURNING
        if status in IDLE_STATES:
            return VacuumActivity.IDLE
        return None

    @property
    def fan_speed(self) -> str:
        """Fan power used for the next clean."""
        return self._fan_speed

    async def _send(self, action: str, fan_power: int | None = None) -> None:
        try:
            await self.coordinator.api.command(action, fan_power)
        except ZigmaError as err:
            raise HomeAssistantError(f"Zigma command '{action}' failed: {err}") from err
        await self.coordinator.async_request_refresh()

    async def async_start(self) -> None:
        """Start cleaning, or resume if paused."""
        if self.activity == VacuumActivity.PAUSED:
            await self._send("resume")
        else:
            await self._send("clean", int(self._fan_speed))

    async def async_pause(self) -> None:
        """Pause the current clean."""
        await self._send("pause")

    async def async_return_to_base(self, **kwargs: Any) -> None:
        """Send the robot back to the dock."""
        await self._send("dock")

    async def async_set_fan_speed(self, fan_speed: str, **kwargs: Any) -> None:
        """Set the fan power for the next clean."""
        self._fan_speed = fan_speed
        self.async_write_ha_state()
