"""Constants for the Nemesis integration."""

from datetime import timedelta

DOMAIN = "inowattio"

CONF_HOST = "host"
CONF_PORT = "port"

DEFAULT_PORT = 6969
SCAN_INTERVAL = timedelta(seconds=3)

ENDPOINT_STATUS = "/status"
ENDPOINT_DATA = "/data"
