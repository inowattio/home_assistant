"""Data update coordinator for Nemesis."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.update_coordinator import UpdateFailed

from .api import NemesisApi
from .api import NemesisApiError
from .const import CONF_HOST
from .const import CONF_PORT
from .const import CONF_SCAN_INTERVAL_SECONDS
from .const import DEFAULT_SCAN_INTERVAL_SECONDS
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class NemesisCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Polls /status and /data on each interval."""

    config_entry_id: str

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        self.config_entry_id = config_entry.entry_id
        host = config_entry.options.get(CONF_HOST, config_entry.data[CONF_HOST])
        port = int(config_entry.options.get(CONF_PORT, config_entry.data[CONF_PORT]))
        scan_interval_seconds = int(
            config_entry.options.get(
                CONF_SCAN_INTERVAL_SECONDS, DEFAULT_SCAN_INTERVAL_SECONDS
            )
        )
        session = async_get_clientsession(hass)
        self.api = NemesisApi(session, host, port)
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval_seconds),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            status = await self.api.get_status()
            data = await self.api.get_data()
        except NemesisApiError as err:
            raise UpdateFailed(str(err)) from err
        return {"status": status, "data": data}
