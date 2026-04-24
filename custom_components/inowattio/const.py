"""Constants for the Nemesis integration."""

DOMAIN = "inowattio"

CONF_HOST = "host"
CONF_PORT = "port"
CONF_SCAN_INTERVAL_SECONDS = "scan_interval_seconds"

DEFAULT_PORT = 6969
DEFAULT_SCAN_INTERVAL_SECONDS = 3
MIN_SCAN_INTERVAL_SECONDS = 3
MAX_SCAN_INTERVAL_SECONDS = 60

ENDPOINT_STATUS = "/status"
ENDPOINT_DATA = "/data"
