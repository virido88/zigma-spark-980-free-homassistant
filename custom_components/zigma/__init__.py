"""The Zigma robot vacuum integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import ZigmaApi
from .const import CONF_TOKEN, DOMAIN
from .coordinator import ZigmaCoordinator, ZigmaScheduleCoordinator

PLATFORMS: list[Platform] = [
    Platform.BUTTON,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TIME,
    Platform.VACUUM,
]


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload so zone buttons match the options."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a robot from a config entry."""
    api = ZigmaApi(
        async_get_clientsession(hass),
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
        entry.data[CONF_TOKEN],
    )
    coordinator = ZigmaCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()

    schedules = ZigmaScheduleCoordinator(hass, entry, api)
    await schedules.async_config_entry_first_refresh()

    data = hass.data.setdefault(DOMAIN, {})
    data[entry.entry_id] = coordinator
    data[f"{entry.entry_id}_schedules"] = schedules
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id)
        hass.data[DOMAIN].pop(f"{entry.entry_id}_schedules")
    return unloaded
