"""Selects: area unit, timezone, and fan power per schedule."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import ZigmaScheduleEntity, ZigmaSettingEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Create selects."""
    extra = hass.data[DOMAIN][f"{entry.entry_id}_extra"]
    async_add_entities([ZigmaAreaUnit(extra, entry), ZigmaTimezone(extra, entry)])

    schedules = hass.data[DOMAIN][f"{entry.entry_id}_schedules"]
    known: set[int] = set()

    @callback
    def _add_new() -> None:
        new = []
        for item in schedules.data or []:
            sid = item.get("id")
            if sid is None or sid in known:
                continue
            known.add(sid)
            new.append(ZigmaScheduleFan(schedules, entry, sid))
        if new:
            async_add_entities(new)

    _add_new()
    entry.async_on_unload(schedules.async_add_listener(_add_new))


class ZigmaAreaUnit(ZigmaSettingEntity, SelectEntity):
    """m2 or ft2."""

    _attr_name = "Flächeneinheit"
    _attr_options = ["m2", "ft2"]
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_area_unit"

    @property
    def current_option(self) -> str | None:
        """Current unit."""
        value = self.settings.get("area_unit")
        return value if value in self._attr_options else None

    async def async_select_option(self, option: str) -> None:
        """Set unit."""
        await self.coordinator.async_set_setting("area_unit", option)


class ZigmaTimezone(ZigmaSettingEntity, SelectEntity):
    """Robot timezone."""

    _attr_name = "Zeitzone"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_timezone"

    @property
    def available(self) -> bool:
        """Only if the robot lists timezones."""
        return super().available and bool(self.settings.get("timezones"))

    @property
    def options(self) -> list[str]:
        """Timezones from the robot."""
        zones = self.settings.get("timezones") or []
        return [z if isinstance(z, str) else str(z.get("name", z)) for z in zones]

    @property
    def current_option(self) -> str | None:
        """Current timezone."""
        value = self.settings.get("timezone")
        return value if value in self.options else None

    async def async_select_option(self, option: str) -> None:
        """Set timezone."""
        await self.coordinator.async_set_setting("timezone", option)


class ZigmaScheduleFan(ZigmaScheduleEntity, SelectEntity):
    """Fan power of one schedule."""

    _attr_options = ["1", "2", "3"]

    def __init__(self, coordinator, entry, schedule_id: int) -> None:
        super().__init__(coordinator, entry, schedule_id)
        self._attr_unique_id = f"{entry.entry_id}_schedule_{schedule_id}_fan"

    @property
    def name(self) -> str | None:
        """Label plus suffix."""
        label = self.schedule.get("label") if self.schedule else None
        return f"{label} Saugstärke" if label else None

    @property
    def current_option(self) -> str | None:
        """Current fan power."""
        value = (self.schedule or {}).get("fan_power")
        return str(value) if value is not None and str(value) in self._attr_options else None

    async def async_select_option(self, option: str) -> None:
        """Set fan power."""
        await self.coordinator.async_update_schedule(self._schedule_id, {"fan_power": int(option)})
