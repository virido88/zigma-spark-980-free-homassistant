"""Constants for the Zigma integration."""

from datetime import timedelta

DOMAIN = "zigma"

CONF_TOKEN = "token"
DEFAULT_PORT = 8765

SCAN_INTERVAL = timedelta(seconds=30)
SCHEDULE_SCAN_INTERVAL = timedelta(seconds=60)
EXTRA_SCAN_INTERVAL = timedelta(minutes=5)
MAP_SCAN_INTERVAL = timedelta(minutes=2)
REQUEST_TIMEOUT = 10

CONF_ZONES = "zones"

FAN_POWERS = ("1", "2", "3")
DEFAULT_FAN_POWER = "3"
