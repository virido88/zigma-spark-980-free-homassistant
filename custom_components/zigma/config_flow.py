"""Config flow: host, port and API token of the robot."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import ZigmaApi, ZigmaAuthError, ZigmaError
from .const import CONF_TOKEN, CONF_ZONES, DEFAULT_PORT, DOMAIN

ZONE_SCHEMA_FIELDS = {
    vol.Required("name"): str,
    vol.Required("x"): vol.All(vol.Coerce(int), vol.Range(min=0, max=20000)),
    vol.Required("y"): vol.All(vol.Coerce(int), vol.Range(min=0, max=20000)),
    vol.Required("width"): vol.All(vol.Coerce(int), vol.Range(min=2, max=20000)),
    vol.Required("height"): vol.All(vol.Coerce(int), vol.Range(min=2, max=20000)),
}

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Required(CONF_TOKEN): str,
    }
)


class ZigmaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle adding a Zigma robot."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for connection data and verify it against the robot."""
        errors: dict[str, str] = {}

        if user_input is not None:
            api = ZigmaApi(
                async_get_clientsession(self.hass),
                user_input[CONF_HOST],
                user_input[CONF_PORT],
                user_input[CONF_TOKEN],
            )
            try:
                status = await api.status()
            except ZigmaAuthError:
                errors["base"] = "invalid_auth"
            except ZigmaError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(
                    f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}"
                )
                self._abort_if_unique_id_configured()
                robot = status.get("robot") or user_input[CONF_HOST]
                return self.async_create_entry(
                    title=f"Zigma {robot}", data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_SCHEMA, user_input
            ),
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> ZigmaOptionsFlow:
        """Zones are managed through the options flow."""
        return ZigmaOptionsFlow()


class ZigmaOptionsFlow(OptionsFlow):
    """Add and remove cleaning zones (rectangles in map cells)."""

    _zones: list[dict[str, Any]]

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose add or remove."""
        self._zones = list(self.config_entry.options.get(CONF_ZONES, []))
        return self.async_show_menu(step_id="init", menu_options=["add_zone", "remove_zone"])

    async def async_step_add_zone(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add a rectangle zone."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if any(z["name"] == user_input["name"] for z in self._zones):
                errors["name"] = "duplicate"
            else:
                self._zones.append(dict(user_input))
                return self.async_create_entry(data={CONF_ZONES: self._zones})
        return self.async_show_form(
            step_id="add_zone",
            data_schema=vol.Schema(ZONE_SCHEMA_FIELDS),
            errors=errors,
        )

    async def async_step_remove_zone(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Remove a zone by name."""
        if not self._zones:
            return self.async_abort(reason="no_zones")
        if user_input is not None:
            self._zones = [z for z in self._zones if z["name"] != user_input["name"]]
            return self.async_create_entry(data={CONF_ZONES: self._zones})
        names = [z["name"] for z in self._zones]
        return self.async_show_form(
            step_id="remove_zone",
            data_schema=vol.Schema({vol.Required("name"): vol.In(names)}),
        )
