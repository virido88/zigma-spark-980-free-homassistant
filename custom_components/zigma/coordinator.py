"""Polls the robot status once per interval."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import ZigmaApi, ZigmaAuthError, ZigmaError
from .const import (
    DOMAIN,
    EXTRA_SCAN_INTERVAL,
    MAP_SCAN_INTERVAL,
    SCAN_INTERVAL,
    SCHEDULE_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


class ZigmaCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Holds the latest /api/status payload."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, api: ZigmaApi) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.api = api

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            return await self.api.status()
        except ZigmaAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except ZigmaError as err:
            raise UpdateFailed(str(err)) from err


class ZigmaScheduleCoordinator(DataUpdateCoordinator[list[dict[str, Any]]]):
    """Holds the robot's schedule list and writes changes back."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, api: ZigmaApi) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_schedules",
            update_interval=SCHEDULE_SCAN_INTERVAL,
        )
        self.api = api
        self._lock = asyncio.Lock()

    async def _async_update_data(self) -> list[dict[str, Any]]:
        try:
            data = await self.api.schedules()
        except ZigmaAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except ZigmaError as err:
            raise UpdateFailed(str(err)) from err
        return data.get("items", [])

    async def async_update_schedule(
        self, schedule_id: int, changes: dict[str, Any]
    ) -> None:
        """Change one schedule. The robot wants the full list, so re-read it first."""
        async with self._lock:
            try:
                current = await self.api.schedules()
                items = current.get("items", [])
                target = next((i for i in items if i.get("id") == schedule_id), None)
                if target is None:
                    raise HomeAssistantError("Schedule no longer exists on the robot")
                target.update(changes)
                saved = await self.api.save_schedules(items)
            except ZigmaError as err:
                raise HomeAssistantError(f"Could not save schedule: {err}") from err
        self.async_set_updated_data(saved.get("items", items))

    async def async_replace_all(self, items: list[dict[str, Any]]) -> None:
        """Write a full schedule list (add or delete)."""
        async with self._lock:
            try:
                saved = await self.api.save_schedules(items)
            except ZigmaError as err:
                raise HomeAssistantError(f"Could not save schedules: {err}") from err
        self.async_set_updated_data(saved.get("items", items))

    async def async_modify(self, fn) -> None:
        """Re-read the list, let fn change it in place, then save it."""
        async with self._lock:
            try:
                items = (await self.api.schedules()).get("items", [])
                fn(items)
                saved = await self.api.save_schedules(items)
            except ZigmaError as err:
                raise HomeAssistantError(f"Could not save schedules: {err}") from err
        self.async_set_updated_data(saved.get("items", items))


class ZigmaExtraCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Settings, events, cleaning history and versions.

    Each part is optional. If one endpoint fails, the others still update.
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, api: ZigmaApi) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_extra",
            update_interval=EXTRA_SCAN_INTERVAL,
        )
        self.api = api

    async def _async_update_data(self) -> dict[str, Any]:
        data: dict[str, Any] = dict(self.data or {})
        ok = False
        for key, call in (
            ("settings", self.api.settings),
            ("events", self.api.events),
            ("sessions", self.api.sessions),
            ("about", self.api.about),
        ):
            try:
                data[key] = await call()
                ok = True
            except ZigmaAuthError as err:
                raise ConfigEntryAuthFailed(str(err)) from err
            except ZigmaError as err:
                _LOGGER.debug("Zigma %s unavailable: %s", key, err)
        if not ok:
            raise UpdateFailed("No extra data available from robot")
        return data

    async def async_set_setting(self, action: str, value: str) -> None:
        """Write one setting and store the answer."""
        try:
            new = await self.api.put_setting(action, value)
        except ZigmaError as err:
            raise HomeAssistantError(f"Could not change setting: {err}") from err
        data = dict(self.data or {})
        if isinstance(new, dict) and new:
            data["settings"] = new
        self.async_set_updated_data(data)


class ZigmaMapCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Holds the robot map (cells, path, dock, zones)."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, api: ZigmaApi) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_map",
            update_interval=MAP_SCAN_INTERVAL,
        )
        self.api = api

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            return await self.api.map_data()
        except ZigmaAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except ZigmaError as err:
            raise UpdateFailed(str(err)) from err
