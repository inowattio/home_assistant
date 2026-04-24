"""Config flow for Nemesis (Zeroconf + manual)."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow
from homeassistant.config_entries import ConfigEntry
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.config_entries import OptionsFlow
from homeassistant.const import CONF_HOST
from homeassistant.const import CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

try:
    from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
except ImportError:
    from homeassistant.components.zeroconf import ZeroconfServiceInfo

from .api import NemesisApi
from .api import NemesisApiError
from .const import CONF_HOST as DATA_HOST
from .const import CONF_PORT as DATA_PORT
from .const import CONF_SCAN_INTERVAL_SECONDS
from .const import DEFAULT_PORT
from .const import DEFAULT_SCAN_INTERVAL_SECONDS
from .const import DOMAIN
from .const import MAX_SCAN_INTERVAL_SECONDS
from .const import MIN_SCAN_INTERVAL_SECONDS

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): vol.Coerce(int),
    }
)

OPTIONS_STEP_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): vol.Coerce(int),
        vol.Required(
            CONF_SCAN_INTERVAL_SECONDS,
            default=DEFAULT_SCAN_INTERVAL_SECONDS,
        ): vol.All(
            vol.Coerce(int),
            vol.Range(
                min=MIN_SCAN_INTERVAL_SECONDS,
                max=MAX_SCAN_INTERVAL_SECONDS,
            ),
        ),
    }
)


def _decode_prop(props: dict[Any, Any] | None, key: str) -> str | None:
    if not props:
        return None
    raw = props.get(key)
    if raw is None:
        raw = props.get(key.encode("utf-8"))
    if raw is None:
        return None
    if isinstance(raw, bytes):
        return raw.decode("utf-8", errors="replace")
    return str(raw)


async def _validate_connection(hass: HomeAssistant, host: str, port: int) -> dict[str, str]:
    session = async_get_clientsession(hass)
    api = NemesisApi(session, host, port)
    status = await api.get_status()
    machine_id = status.get("id")
    if not machine_id or not isinstance(machine_id, str):
        raise NemesisApiError("Status response missing string 'id'")
    await api.get_data()
    return {"title": f"Nemesis ({machine_id})", "machine_id": machine_id}


class NemesisConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle Zeroconf discovery and manual host entry."""

    VERSION = 1

    def __init__(self) -> None:
        self._discovered_host: str | None = None
        self._discovered_port: int = DEFAULT_PORT

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> NemesisOptionsFlow:
        return NemesisOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                info = await _validate_connection(
                    self.hass, user_input[CONF_HOST], user_input[CONF_PORT]
                )
            except NemesisApiError as err:
                _LOGGER.warning("Manual setup failed: %s", err)
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(info["machine_id"])
                self._abort_if_unique_id_configured(
                    updates={
                        DATA_HOST: user_input[CONF_HOST],
                        DATA_PORT: user_input[CONF_PORT],
                    }
                )
                return self.async_create_entry(
                    title=info["title"],
                    data={
                        DATA_HOST: user_input[CONF_HOST],
                        DATA_PORT: user_input[CONF_PORT],
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        host = str(discovery_info.ip_address)
        port = discovery_info.port or DEFAULT_PORT
        machine_id = _decode_prop(discovery_info.properties, "machine_id")

        self._discovered_host = host
        self._discovered_port = port

        if machine_id:
            await self.async_set_unique_id(machine_id)
            self._abort_if_unique_id_configured(
                updates={DATA_HOST: host, DATA_PORT: port},
            )

        self.context["title_placeholders"] = {
            "host": host,
            "port": str(port),
        }
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        host = self._discovered_host
        port = self._discovered_port
        if host is None:
            return self.async_abort(reason="no_host")

        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                info = await _validate_connection(self.hass, host, port)
            except NemesisApiError as err:
                _LOGGER.warning("Discovery confirm failed: %s", err)
                errors["base"] = "cannot_connect"
            else:
                unique_id = info["machine_id"]
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured(
                    updates={DATA_HOST: host, DATA_PORT: port},
                )
                return self.async_create_entry(
                    title=info["title"],
                    data={DATA_HOST: host, DATA_PORT: port},
                )

        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={"host": host, "port": str(port)},
            errors=errors,
        )


class NemesisOptionsFlow(OptionsFlow):
    """Handle options for the Nemesis integration."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                await _validate_connection(
                    self.hass, user_input[CONF_HOST], user_input[CONF_PORT]
                )
            except NemesisApiError as err:
                _LOGGER.warning("Options update failed: %s", err)
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title="",
                    data={
                        CONF_HOST: user_input[CONF_HOST],
                        CONF_PORT: user_input[CONF_PORT],
                        CONF_SCAN_INTERVAL_SECONDS: user_input[
                            CONF_SCAN_INTERVAL_SECONDS
                        ],
                    },
                )

        current_host = self.config_entry.options.get(
            CONF_HOST, self.config_entry.data[CONF_HOST]
        )
        current_port = self.config_entry.options.get(
            CONF_PORT, self.config_entry.data[CONF_PORT]
        )
        current_scan_interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL_SECONDS, DEFAULT_SCAN_INTERVAL_SECONDS
        )
        schema = self.add_suggested_values_to_schema(
            OPTIONS_STEP_DATA_SCHEMA,
            {
                CONF_HOST: current_host,
                CONF_PORT: current_port,
                CONF_SCAN_INTERVAL_SECONDS: current_scan_interval,
            },
        )

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors,
        )
