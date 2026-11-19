"""Buttons that start a cleaning run for one configured zone."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import ZigmaError
from .const import CONF_ZONES, DOMAIN
from .coordinator import ZigmaCoordinator

# Same states the robot accepts for area cleaning (see robot agent issue_area).
AREA_OK_STATES = {
    "charging",
    "PileCharging",
    "DirCharging",
    "Standby",
    "idle",
    "Pause",
    "paused",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create one button per configured zone."""
    coordinator: ZigmaCoordinator = hass.data[DOMAIN][entry.entry_id]
    zones = entry.options.get(CONF_ZONES, [])
    async_add_entities(ZigmaZoneButton(coordinator, entry, zone) for zone in zones)


class ZigmaZoneButton(ButtonEntity):
    """Start cleaning of one rectangle zone."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: ZigmaCoordinator, entry: ConfigEntry, zone: dict
    ) -> None:
        self.coordinator = coordinator
        self._zone = dict(zone)
        self._attr_name = f"{zone['name']} saugen"
        self._attr_unique_id = f"{entry.entry_id}_zone_{zone['name']}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer="Zigma",
            name=entry.title,
        )

    async def async_press(self) -> None:
        """Check robot state and map, then send area_clean for this zone."""
        status = self.coordinator.data or {}
        work = status.get("working_status")
        if status.get("error") not in (None, "NoError"):
            raise HomeAssistantError(f"Roboter meldet Fehler: {status.get('error')}")
        if work not in AREA_OK_STATES:
            raise HomeAssistantError(
                f"Flächenreinigung nur im Dock, im Standby oder pausiert möglich (aktuell: {work})"
            )

        api = self.coordinator.api
        try:
            mp = await api.map_data()
            if not mp.get("available"):
                raise HomeAssistantError("Karte ist gerade nicht verfügbar")
            context = {
                "map_id": mp.get("map_id"),
                "width": mp.get("width"),
                "height": mp.get("height"),
                "map_origin": mp.get("map_origin"),
            }
            rect = {
                "x": self._zone["x"],
                "y": self._zone["y"],
                "width": self._zone["width"],
                "height": self._zone["height"],
            }
            await api.command("area_clean", rect=rect, map_context=context)
        except ZigmaError as err:
            raise HomeAssistantError(f"Flächenreinigung fehlgeschlagen: {err}") from err

        await self.coordinator.async_request_refresh()
