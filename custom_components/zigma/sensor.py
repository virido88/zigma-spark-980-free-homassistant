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
from .entity import ZigmaEntity


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
