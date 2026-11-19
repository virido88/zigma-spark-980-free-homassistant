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
from .const import DOMAIN, SCAN_INTERVAL, SCHEDULE_SCAN_INTERVAL

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
