"""Services: full schedule control, area clean and no-go zones."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv

from .api import ZigmaError
from .const import DOMAIN
from .coordinator import ZigmaCoordinator

# Same states the robot accepts for area cleaning (see robot agent issue_area).
AREA_OK_STATES = {
    "charging",
    "PileCharging",
    "DirCharging",
    "Standby",
    "idle",
    "Pause",
    "paused",
}

# Risky schedule actions (reboot, restore_master, custom_command) are NOT offered.
SAFE_ACTIONS = ("clean", "dock", "random_song", "play_song")
RESTRICTIONS = ("all", "mop", "vacuum")

ATTR_ENTRY = "entry_id"
_ENTRY = {vol.Optional(ATTR_ENTRY): cv.string}
_DAYS = vol.All(
    cv.ensure_list,
    [vol.All(vol.Coerce(int), vol.Range(min=0, max=6))],
    vol.Length(min=1, max=7),
)
_TIME = vol.Match(r"^([01]\d|2[0-3]):[0-5]\d$")
_FAN = vol.All(vol.Coerce(int), vol.Range(min=1, max=3))
_RECT = {
    vol.Required("x"): vol.All(vol.Coerce(int), vol.Range(min=0)),
    vol.Required("y"): vol.All(vol.Coerce(int), vol.Range(min=0)),
    vol.Required("width"): vol.All(vol.Coerce(int), vol.Range(min=2)),
    vol.Required("height"): vol.All(vol.Coerce(int), vol.Range(min=2)),
}

UPDATE_SCHEDULE = vol.Schema(
    {
        **_ENTRY,
        vol.Required("schedule_id"): vol.Coerce(int),
        vol.Optional("label"): vol.All(cv.string, vol.Length(min=1, max=72)),
        vol.Optional("time"): _TIME,
        vol.Optional("days"): _DAYS,
        vol.Optional("enabled"): cv.boolean,
        vol.Optional("action"): vol.In(SAFE_ACTIONS),
        vol.Optional("fan_power"): _FAN,
        vol.Optional("song"): cv.string,
    }
)
ADD_SCHEDULE = vol.Schema(
    {
        **_ENTRY,
        vol.Required("label"): vol.All(cv.string, vol.Length(min=1, max=72)),
        vol.Required("time"): _TIME,
        vol.Required("days"): _DAYS,
        vol.Optional("enabled", default=True): cv.boolean,
        vol.Optional("action", default="clean"): vol.In(SAFE_ACTIONS),
        vol.Optional("fan_power", default=3): _FAN,
        vol.Optional("song"): cv.string,
    }
)
DELETE_SCHEDULE = vol.Schema({**_ENTRY, vol.Required("schedule_id"): vol.Coerce(int)})
CLEAN_AREA = vol.Schema({**_ENTRY, **_RECT})
NO_GO_ZONE = vol.Schema(
    {
        **_ENTRY,
        vol.Required("operation"): vol.In(("add", "update", "delete")),
        vol.Optional("index"): vol.All(vol.Coerce(int), vol.Range(min=0)),
        vol.Optional("x"): vol.All(vol.Coerce(int), vol.Range(min=0)),
        vol.Optional("y"): vol.All(vol.Coerce(int), vol.Range(min=0)),
        vol.Optional("width"): vol.All(vol.Coerce(int), vol.Range(min=2)),
        vol.Optional("height"): vol.All(vol.Coerce(int), vol.Range(min=2)),
        vol.Optional("restriction", default="all"): vol.In(RESTRICTIONS),
    }
)


def _entry_id(hass: HomeAssistant, call: ServiceCall) -> str:
    """Pick the config entry. Default: the only one."""
    loaded = hass.data.get(DOMAIN, {})
    entries = [e.entry_id for e in hass.config_entries.async_entries(DOMAIN) if e.entry_id in loaded]
    wanted = call.data.get(ATTR_ENTRY)
    if wanted:
        if wanted not in entries:
            raise HomeAssistantError(f"Unknown Zigma entry: {wanted}")
        return wanted
    if len(entries) != 1:
        raise HomeAssistantError("More than one robot. Set entry_id.")
    return entries[0]


def _map_context(mp: dict[str, Any]) -> dict[str, Any]:
    return {
        "map_id": mp.get("map_id"),
        "width": mp.get("width"),
        "height": mp.get("height"),
        "map_origin": mp.get("map_origin"),
    }


async def async_clean_area(coordinator: ZigmaCoordinator, rect: dict[str, int]) -> None:
    """Check robot state and map, then send area_clean."""
    status = coordinator.data or {}
    work = status.get("working_status")
    if status.get("error") not in (None, "NoError"):
        raise HomeAssistantError(f"Roboter meldet Fehler: {status.get('error')}")
    if work not in AREA_OK_STATES:
        raise HomeAssistantError(
            f"Flächenreinigung nur im Dock, im Standby oder pausiert möglich (aktuell: {work})"
        )
    api = coordinator.api
    try:
        mp = await api.map_data()
        if not mp.get("available"):
            raise HomeAssistantError("Karte ist gerade nicht verfügbar")
        await api.command("area_clean", rect=rect, map_context=_map_context(mp))
    except ZigmaError as err:
        raise HomeAssistantError(f"Flächenreinigung fehlgeschlagen: {err}") from err
    await coordinator.async_request_refresh()


def async_register_services(hass: HomeAssistant) -> None:
    """Register services once."""
    if hass.services.has_service(DOMAIN, "update_schedule"):
        return

    def _schedules(call: ServiceCall):
        return hass.data[DOMAIN][f"{_entry_id(hass, call)}_schedules"]

    def _fields(data: dict[str, Any]) -> dict[str, Any]:
        out = {
            k: data[k]
            for k in ("label", "time", "days", "enabled", "action", "fan_power", "song")
            if k in data
        }
        if "days" in out:
            out["days"] = sorted(set(out["days"]))
        return out

    async def update_schedule(call: ServiceCall) -> None:
        changes = _fields(call.data)
        if not changes:
            raise HomeAssistantError("Nothing to change")
        await _schedules(call).async_update_schedule(call.data["schedule_id"], changes)

    async def add_schedule(call: ServiceCall) -> None:
        item = _fields(call.data)
        if item["action"] == "play_song" and not item.get("song"):
            raise HomeAssistantError("play_song needs a song")

        def _add(items: list[dict[str, Any]]) -> None:
            if len(items) >= 24:
                raise HomeAssistantError("Robot allows at most 24 schedules")
            items.append(item)

        await _schedules(call).async_modify(_add)

    async def delete_schedule(call: ServiceCall) -> None:
        sid = call.data["schedule_id"]

        def _delete(items: list[dict[str, Any]]) -> None:
            if not any(i.get("id") == sid for i in items):
                raise HomeAssistantError("Schedule no longer exists on the robot")
            items[:] = [i for i in items if i.get("id") != sid]

        await _schedules(call).async_modify(_delete)

    async def clean_area(call: ServiceCall) -> None:
        eid = _entry_id(hass, call)
        rect = {k: call.data[k] for k in ("x", "y", "width", "height")}
        await async_clean_area(hass.data[DOMAIN][eid], rect)

    async def set_no_go_zone(call: ServiceCall) -> None:
        eid = _entry_id(hass, call)
        coordinator: ZigmaCoordinator = hass.data[DOMAIN][eid]
        op = call.data["operation"]
        if op in ("update", "delete") and "index" not in call.data:
            raise HomeAssistantError("index is needed for update and delete")
        if op in ("add", "update") and not all(
            k in call.data for k in ("x", "y", "width", "height")
        ):
            raise HomeAssistantError("x, y, width and height are needed")
        work = (coordinator.data or {}).get("working_status")
        if work not in AREA_OK_STATES:
            raise HomeAssistantError(f"No-go zones only change while robot is idle (now: {work})")
        restriction = call.data["restriction"]
        body: dict[str, Any] = {"operation": op}
        if "index" in call.data:
            body["index"] = call.data["index"]
        if op != "delete":
            body["rect"] = {k: call.data[k] for k in ("x", "y", "width", "height")}
            # EXPERIMENTAL: flag meaning guessed from the web UI (can_clean=vacuum ok).
            body["flags"] = {
                "can_clean": restriction == "mop",
                "can_mop": restriction == "vacuum",
            }
        try:
            mp = await coordinator.api.map_data()
            if not mp.get("available"):
                raise HomeAssistantError("Karte ist gerade nicht verfügbar")
            body["base_zones"] = mp.get("zones") or []
            body["map_context"] = _map_context(mp)
            await coordinator.api.command("set_forbidden", **body)
        except ZigmaError as err:
            raise HomeAssistantError(f"No-go zone failed: {err}") from err
        await hass.data[DOMAIN][f"{eid}_map"].async_request_refresh()

    reg = hass.services.async_register
    reg(DOMAIN, "update_schedule", update_schedule, UPDATE_SCHEDULE)
    reg(DOMAIN, "add_schedule", add_schedule, ADD_SCHEDULE)
    reg(DOMAIN, "delete_schedule", delete_schedule, DELETE_SCHEDULE)
    reg(DOMAIN, "clean_area", clean_area, CLEAN_AREA)
    reg(DOMAIN, "set_no_go_zone", set_no_go_zone, NO_GO_ZONE)
