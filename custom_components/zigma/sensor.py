"""Sensors for battery, status, last clean and Wi-Fi."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    UnitOfArea,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import ZigmaCoordinator
from .entity import ZigmaEntity, ZigmaSettingEntity


@dataclass(frozen=True, kw_only=True)
class ZigmaSensorDescription(SensorEntityDescription):
    """Sensor description with a function that extracts the value."""

    value_fn: Callable[[dict[str, Any]], Any]


SENSORS: tuple[ZigmaSensorDescription, ...] = (
    ZigmaSensorDescription(
        key="battery",
        name="Akku",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get("battery_level"),
    ),
    ZigmaSensorDescription(
        key="working_status",
        name="Status",
        value_fn=lambda d: d.get("working_status"),
    ),
    ZigmaSensorDescription(
        key="clean_area",
        name="Letzte Reinigung Fläche",
        device_class=SensorDeviceClass.AREA,
        native_unit_of_measurement=UnitOfArea.SQUARE_METERS,
        value_fn=lambda d: d.get("clean_area_m2"),
    ),
    ZigmaSensorDescription(
        key="clean_time",
        name="Letzte Reinigung Dauer",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        value_fn=lambda d: d.get("clean_time_s"),
    ),
    ZigmaSensorDescription(
        key="error",
        name="Fehler",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.get("error"),
    ),
    ZigmaSensorDescription(
        key="wifi_signal",
        name="WLAN-Signal",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: (d.get("wifi") or {}).get("signal_dbm"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the sensors for this robot."""
    coordinator: ZigmaCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(ZigmaSensor(coordinator, entry, desc) for desc in SENSORS)
    extra = hass.data[DOMAIN][f"{entry.entry_id}_extra"]
    async_add_entities(
        [
            ZigmaLastSessionSensor(extra, entry),
            ZigmaSessionCountSensor(extra, entry),
            ZigmaLastEventSensor(extra, entry),
            ZigmaVersionsSensor(extra, entry),
        ]
    )


class ZigmaSensor(ZigmaEntity, SensorEntity):
    """A single value from the robot status."""

    entity_description: ZigmaSensorDescription

    def __init__(
        self,
        coordinator: ZigmaCoordinator,
        entry: ConfigEntry,
        description: ZigmaSensorDescription,
    ) -> None:
        super().__init__(coordinator, entry)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

    @property
    def native_value(self) -> Any:
        """Return the current value."""
        return self.entity_description.value_fn(self.coordinator.data or {})


def _items(data: dict[str, Any] | None, key: str) -> list[dict[str, Any]]:
    block = (data or {}).get(key) or {}
    items = block.get("items") if isinstance(block, dict) else None
    return [i for i in (items or []) if isinstance(i, dict)]


class ZigmaLastSessionSensor(ZigmaSettingEntity, SensorEntity):
    """Outcome of the latest cleaning run, with its stats as attributes."""

    _attr_name = "Letzter Reinigungsbericht"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_last_session"

    def _last(self) -> dict[str, Any] | None:
        items = _items(self.coordinator.data, "sessions")
        return max(items, key=lambda i: i.get("started") or 0, default=None)

    @property
    def native_value(self) -> str | None:
        """Outcome text."""
        last = self._last()
        return last.get("outcome") if last else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Stats of that run."""
        last = self._last() or {}
        return {
            k: last.get(k)
            for k in ("id", "started", "ended", "clean_area_m2", "clean_time_s", "time_basis")
        }


class ZigmaSessionCountSensor(ZigmaSettingEntity, SensorEntity):
    """How many cleaning runs the robot recorded."""

    _attr_name = "Reinigungen gesamt"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_session_count"

    @property
    def native_value(self) -> int | None:
        """Number of recorded runs."""
        if "sessions" not in (self.coordinator.data or {}):
            return None
        return len(_items(self.coordinator.data, "sessions"))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Last 10 runs."""
        items = sorted(
            _items(self.coordinator.data, "sessions"),
            key=lambda i: i.get("started") or 0,
            reverse=True,
        )
        return {"recent": items[:10]}


class ZigmaLastEventSensor(ZigmaSettingEntity, SensorEntity):
    """Latest robot event. The recent log is in the attributes."""

    _attr_name = "Letztes Ereignis"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_last_event"

    def _events(self) -> list[dict[str, Any]]:
        return sorted(
            _items(self.coordinator.data, "events"),
            key=lambda i: i.get("timestamp") or 0,
            reverse=True,
        )

    @property
    def native_value(self) -> str | None:
        """Message of the newest event (max 255 chars for HA state)."""
        events = self._events()
        return (events[0].get("message") or "")[:255] if events else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Recent events, newest first."""
        return {"events": self._events()[:20]}


class ZigmaVersionsSensor(ZigmaSettingEntity, SensorEntity):
    """Installed robot software. State is the agent version."""

    _attr_name = "Software"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_software"

    @property
    def native_value(self) -> str | None:
        """Version of the first component."""
        items = _items(self.coordinator.data, "about")
        return str(items[0].get("version")) if items and items[0].get("version") else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """All components by name."""
        return {
            str(i.get("name")): i.get("version")
            for i in _items(self.coordinator.data, "about")
            if i.get("name")
        }
