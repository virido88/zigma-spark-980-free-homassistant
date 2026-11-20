"""Buttons: start a cleaning run for one zone, and sync the robot clock."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_ZONES, DOMAIN
from .coordinator import ZigmaCoordinator, ZigmaExtraCoordinator
from .services import async_clean_area


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create one button per configured zone plus the NTP sync button."""
    coordinator: ZigmaCoordinator = hass.data[DOMAIN][entry.entry_id]
    extra: ZigmaExtraCoordinator = hass.data[DOMAIN][f"{entry.entry_id}_extra"]
    zones = entry.options.get(CONF_ZONES, [])
    entities: list[ButtonEntity] = [ZigmaZoneButton(coordinator, entry, z) for z in zones]
    entities.append(ZigmaNtpSyncButton(extra, entry))
    async_add_entities(entities)


def _device(entry: ConfigEntry) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        manufacturer="Zigma",
        name=entry.title,
    )


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
        self._attr_device_info = _device(entry)

    async def async_press(self) -> None:
        """Send area_clean for this zone."""
        rect = {k: self._zone[k] for k in ("x", "y", "width", "height")}
        await async_clean_area(self.coordinator, rect)


class ZigmaNtpSyncButton(ButtonEntity):
    """Ask the robot to sync its clock now."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_name = "Uhrzeit synchronisieren"

    def __init__(self, extra: ZigmaExtraCoordinator, entry: ConfigEntry) -> None:
        self._extra = extra
        self._attr_unique_id = f"{entry.entry_id}_ntp_sync"
        self._attr_device_info = _device(entry)

    async def async_press(self) -> None:
        """Send the ntp_sync action."""
        await self._extra.async_set_setting("ntp_sync", "true")
