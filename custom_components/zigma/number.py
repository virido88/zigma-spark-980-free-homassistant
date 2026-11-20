"""Number: robot volume."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import ZigmaSettingEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Create the volume number."""
    async_add_entities([ZigmaVolume(hass.data[DOMAIN][f"{entry.entry_id}_extra"], entry)])


class ZigmaVolume(ZigmaSettingEntity, NumberEntity):
    """Robot speaker volume, 0-100."""

    _attr_name = "Lautstärke"
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_mode = NumberMode.SLIDER
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_volume"

    @property
    def available(self) -> bool:
        """Only if the robot reports a volume."""
        return super().available and self.settings.get("volume") is not None

    @property
    def native_value(self) -> float | None:
        """Current volume."""
        value = self.settings.get("volume")
        return float(value) if value is not None else None

    async def async_set_native_value(self, value: float) -> None:
        """Set volume."""
        await self.coordinator.async_set_setting("volume", str(int(value)))
