"""Minimal async client for the Zigma robot web API (port 8765)."""

from __future__ import annotations

import asyncio
from typing import Any

import aiohttp

from .const import REQUEST_TIMEOUT


class ZigmaError(Exception):
    """Robot could not be reached or returned an error."""


class ZigmaAuthError(ZigmaError):
    """Token was rejected by the robot."""


class ZigmaApi:
    """Talks to the robot agent over HTTP with a Bearer token."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        host: str,
        port: int,
        token: str,
    ) -> None:
        self._session = session
        self._base = f"http://{host}:{port}"
        self._headers = {
            "Authorization": f"Bearer {token}",
            # Robot rejects non-GET requests without this header.
            "X-Zigma-Request": "1",
        }

    async def _request(
        self, method: str, path: str, json: dict[str, Any] | None = None
    ) -> Any:
        try:
            async with self._session.request(
                method,
                self._base + path,
                headers=self._headers,
                json=json,
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
            ) as resp:
                if resp.status in (401, 403):
                    raise ZigmaAuthError("Token rejected by robot")
                if resp.status >= 400:
                    text = await resp.text()
                    raise ZigmaError(f"HTTP {resp.status}: {text[:200]}")
                return await resp.json(content_type=None)
        except ZigmaError:
            raise
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise ZigmaError(f"Cannot reach robot: {err}") from err

    async def status(self) -> dict[str, Any]:
        """Return the current robot status (GET /api/status)."""
        return await self._request("GET", "/api/status")

    async def command(
        self, action: str, fan_power: int | None = None, **extra: Any
    ) -> dict[str, Any]:
        """Send a command (POST /api/commands): clean, pause, resume, dock, area_clean."""
        body: dict[str, Any] = {"action": action, **extra}
        if fan_power is not None:
            body["fan_power"] = fan_power
        return await self._request("POST", "/api/commands", json=body)

    async def map_data(self) -> dict[str, Any]:
        """Return the current map (GET /api/map), incl. map_id, size and origin."""
        return await self._request("GET", "/api/map")

    async def schedules(self) -> dict[str, Any]:
        """Return all schedules (GET /api/schedules)."""
        return await self._request("GET", "/api/schedules")

    async def save_schedules(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        """Replace the full schedule list (PUT /api/schedules)."""
        return await self._request("PUT", "/api/schedules", json={"items": items})

    async def settings(self) -> dict[str, Any]:
        """Return robot settings (GET /api/settings)."""
        return await self._request("GET", "/api/settings")

    async def put_setting(self, action: str, value: str) -> dict[str, Any]:
        """Change one setting (PUT /api/settings). Value is always a string."""
        return await self._request(
            "PUT", "/api/settings", json={"action": action, "value": value}
        )

    async def events(self) -> dict[str, Any]:
        """Return the last robot events (GET /api/events)."""
        return await self._request("GET", "/api/events")

    async def sessions(self) -> dict[str, Any]:
        """Return the cleaning history (GET /api/sessions)."""
        return await self._request("GET", "/api/sessions")

    async def about(self) -> dict[str, Any]:
        """Return installed component versions (GET /api/about)."""
        return await self._request("GET", "/api/about")
