"""Image entity: the robot map as PNG (same colors as the Zigma web UI)."""

from __future__ import annotations

import struct
import zlib
from typing import Any

from homeassistant.components.image import ImageEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import ZigmaMapCoordinator

# Palette from the web UI: 0 light, 1 green, 2 tan, 3 not drawn (transparent).
PALETTE: dict[int, tuple[int, int, int, int]] = {
    0: (0xFA, 0xFA, 0xF5, 255),
    1: (0xB8, 0xC3, 0xAF, 255),
    2: (0xD9, 0xBD, 0x8B, 255),
    3: (0, 0, 0, 0),
}
PATH_COLOR = (0x2F, 0x6F, 0xD0, 255)
DOCK_COLOR = (0xD0, 0x30, 0x30, 255)
ZONE_COLOR = (0xE0, 0x20, 0x20, 255)
MAX_SIDE = 800


def _png(width: int, height: int, rgba: bytes) -> bytes:
    """Encode RGBA bytes as PNG without extra libraries."""

    def chunk(tag: bytes, body: bytes) -> bytes:
        crc = zlib.crc32(tag + body) & 0xFFFFFFFF
        return struct.pack(">I", len(body)) + tag + body + struct.pack(">I", crc)

    stride = width * 4
    raw = b"".join(b"\x00" + rgba[y * stride : (y + 1) * stride] for y in range(height))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 6))
        + chunk(b"IEND", b"")
    )


def _rect_of(zone: Any) -> tuple[int, int, int, int] | None:
    """Pull x, y, width, height out of a zone dict (shape not fully known)."""
    if not isinstance(zone, dict):
        return None
    src = zone.get("rect") if isinstance(zone.get("rect"), dict) else zone
    try:
        return (int(src["x"]), int(src["y"]), int(src["width"]), int(src["height"]))
    except (KeyError, TypeError, ValueError):
        return None


def render_map(mp: dict[str, Any]) -> bytes | None:
    """Draw cells, path, dock and no-go zones into a PNG."""
    width, height, cells = mp.get("width"), mp.get("height"), mp.get("cells")
    if not (isinstance(width, int) and isinstance(height, int) and cells):
        return None
    if width < 1 or height < 1 or len(cells) < width * height:
        return None
    scale = max(1, min(8, MAX_SIDE // max(width, height)))
    out_w, out_h = width * scale, height * scale
    buf = bytearray(out_w * out_h * 4)

    def put(px: int, py: int, color: tuple[int, int, int, int]) -> None:
        if 0 <= px < out_w and 0 <= py < out_h:
            i = (py * out_w + px) * 4
            buf[i : i + 4] = bytes(color)

    def cell(cx: int, cy: int, color: tuple[int, int, int, int]) -> None:
        for dy in range(scale):
            for dx in range(scale):
                put(cx * scale + dx, cy * scale + dy, color)

    for y in range(height):
        row = bytearray()
        for x in range(width):
            row += bytes(PALETTE.get(cells[y * width + x], PALETTE[3]))
        for dy in range(scale):
            line = bytearray()
            for x in range(width):
                line += row[x * 4 : x * 4 + 4] * scale
            start = ((y * scale + dy) * out_w) * 4
            buf[start : start + out_w * 4] = line

    for p in mp.get("path") or []:
        if isinstance(p, dict) and "x" in p and "y" in p:
            cell(int(p["x"]), int(p["y"]), PATH_COLOR)
    dock = mp.get("dock")
    if isinstance(dock, dict) and "x" in dock and "y" in dock:
        for ox in range(-1, 2):
            for oy in range(-1, 2):
                cell(int(dock["x"]) + ox, int(dock["y"]) + oy, DOCK_COLOR)

    origin = mp.get("map_origin") or [0, 0]
    for zone in mp.get("zones") or []:
        rect = _rect_of(zone)
        if not rect:
            continue
        x0 = (rect[0] + origin[0]) * scale
        y0 = (rect[1] + origin[1]) * scale
        x1 = x0 + rect[2] * scale
        y1 = y0 + rect[3] * scale
        for px in range(x0, x1 + 1):
            put(px, y0, ZONE_COLOR)
            put(px, y1, ZONE_COLOR)
        for py in range(y0, y1 + 1):
            put(x0, py, ZONE_COLOR)
            put(x1, py, ZONE_COLOR)
    return _png(out_w, out_h, bytes(buf))


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Create the map image."""
    coordinator: ZigmaMapCoordinator = hass.data[DOMAIN][f"{entry.entry_id}_map"]
    async_add_entities([ZigmaMapImage(hass, coordinator, entry)])


class ZigmaMapImage(ImageEntity):
    """The current robot map."""

    _attr_has_entity_name = True
    _attr_name = "Karte"
    _attr_content_type = "image/png"

    def __init__(
        self, hass: HomeAssistant, coordinator: ZigmaMapCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(hass)
        self._coordinator = coordinator
        self._png: bytes | None = None
        self._map_key: Any = None
        self._attr_unique_id = f"{entry.entry_id}_map"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer="Zigma",
            name=entry.title,
        )

    async def async_added_to_hass(self) -> None:
        """Follow the map coordinator."""
        self.async_on_remove(self._coordinator.async_add_listener(self._handle_update))
        self._handle_update()

    def _handle_update(self) -> None:
        mp = self._coordinator.data or {}
        key = (mp.get("map_id"), len(mp.get("path") or []), repr(mp.get("zones")), mp.get("dock"))
        if key != self._map_key:
            self._map_key = key
            self._png = None
            self._attr_image_last_updated = dt_util.utcnow()
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Needs a readable map."""
        mp = self._coordinator.data or {}
        return self._coordinator.last_update_success and bool(mp.get("available"))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Map facts, e.g. for use in cards."""
        mp = self._coordinator.data or {}
        return {
            "map_id": mp.get("map_id"),
            "width": mp.get("width"),
            "height": mp.get("height"),
            "map_origin": mp.get("map_origin"),
            "dock": mp.get("dock"),
            "zones": mp.get("zones"),
        }

    async def async_image(self) -> bytes | None:
        """Render once per change, off the event loop."""
        if self._png is None:
            self._png = await self.hass.async_add_executor_job(
                render_map, self._coordinator.data or {}
            )
        return self._png
