"""Text: robot name and NTP server."""

from __future__ import annotations

from homeassistant.components.text import TextEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import ZigmaSettingEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Create the text entities."""
    extra = hass.data[DOMAIN][f"{entry.entry_id}_extra"]
    async_add_entities(
        [
            ZigmaSettingText(extra, entry, "robot_name", "Name", "name", 96),
            ZigmaSettingText(extra, entry, "ntp_server", "NTP-Server", "ntp_server", 128),
        ]
    )


class ZigmaSettingText(ZigmaSettingEntity, TextEntity):
    """A text setting."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, entry, key: str, name: str, action: str, max_len: int) -> None:
        super().__init__(coordinator, entry)
        self._key = key
        self._action = action
        self._attr_name = name
        self._attr_native_max = max_len
        self._attr_native_min = 1
        self._attr_unique_id = f"{entry.entry_id}_{key}"

    @property
    def available(self) -> bool:
        """Only if the robot reports the setting and allows edits."""
        return (
            super().available
            and self.settings.get(self._key) is not None
            and self.settings.get("editable", True) is not False
        )

    @property
    def native_value(self) -> str | None:
        """Current value."""
        return self.settings.get(self._key)

    async def async_set_value(self, value: str) -> None:
        """Write value."""
        await self.coordinator.async_set_setting(self._action, value)
