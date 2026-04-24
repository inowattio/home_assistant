"""Sensors from Nemesis /status and /data."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from typing import Callable

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.components.sensor import SensorEntity
from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.components.sensor import SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.const import EntityCategory
from homeassistant.const import UnitOfEnergy
from homeassistant.const import UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import http_base_url
from .const import CONF_HOST
from .const import CONF_PORT
from .const import DOMAIN
from .const import ENDPOINT_STATUS
from .coordinator import NemesisCoordinator


@dataclass(frozen=True)
class NemesisSensorTemplate:
    """Pairs a Home Assistant description with a value resolver."""

    description: SensorEntityDescription
    value_fn: Callable[[dict[str, Any]], StateType]


def _ctx(data: dict[str, Any]) -> dict[str, Any]:
    status = data.get("status") or {}
    ctx = status.get("context")
    return ctx if isinstance(ctx, dict) else {}


def _short_machine_id(data: dict[str, Any]) -> str | None:
    raw = (data.get("status") or {}).get("id")
    if not isinstance(raw, str) or not raw:
        return None
    if len(raw) <= 12:
        return raw
    return f"{raw[:8]}…{raw[-4:]}"


def _data_field(key: str) -> Callable[[dict[str, Any]], StateType]:
    def _get(d: dict[str, Any]) -> StateType:
        return (d.get("data") or {}).get(key)

    return _get


def _power_sensor(key: str, translation_key: str) -> NemesisSensorTemplate:
    return NemesisSensorTemplate(
        SensorEntityDescription(
            key=key,
            translation_key=translation_key,
            native_unit_of_measurement=UnitOfPower.WATT,
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_display_precision=0,
        ),
        value_fn=_data_field(key),
    )


def _energy_sensor(key: str, translation_key: str) -> NemesisSensorTemplate:
    return NemesisSensorTemplate(
        SensorEntityDescription(
            key=key,
            translation_key=translation_key,
            native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
            suggested_display_precision=0,
        ),
        value_fn=_data_field(key),
    )


def _ratio_percent(key: str) -> Callable[[dict[str, Any]], StateType]:
    """Convert a 0..1 fraction from /data into a 0..100 percentage."""

    def _get(d: dict[str, Any]) -> StateType:
        raw = (d.get("data") or {}).get(key)
        if raw is None:
            return None
        try:
            return round(float(raw) * 100, 1)
        except (TypeError, ValueError):
            return None

    return _get


def _fraction_sensor(key: str, translation_key: str) -> NemesisSensorTemplate:
    return NemesisSensorTemplate(
        SensorEntityDescription(
            key=key,
            translation_key=translation_key,
            native_unit_of_measurement=PERCENTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_display_precision=0,
        ),
        value_fn=_ratio_percent(key),
    )


SENSOR_TEMPLATES: tuple[NemesisSensorTemplate, ...] = (
    _power_sensor("grid_w", "grid_power"),
    _energy_sensor("grid_wh_abs", "grid_energy_imported"),
    _energy_sensor("grid_wh_inj", "grid_energy_exported"),
    _power_sensor("load_w", "load_power"),
    _energy_sensor("load_wh", "load_energy"),
    _fraction_sensor("load_from_grid_per", "load_from_grid_per"),
    _power_sensor("battery_w", "battery_power"),
    NemesisSensorTemplate(
        SensorEntityDescription(
            key="battery_soc",
            translation_key="battery_soc",
            native_unit_of_measurement=PERCENTAGE,
            device_class=SensorDeviceClass.BATTERY,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_display_precision=0,
        ),
        value_fn=_data_field("battery_soc"),
    ),
    _energy_sensor("battery_wh_abs", "battery_energy_charged"),
    _energy_sensor("battery_wh_inj", "battery_energy_discharged"),
    _power_sensor("pv", "pv_power"),
    _energy_sensor("pv_wh", "pv_energy"),
    _fraction_sensor("pv_pot", "pv_potential"),
    NemesisSensorTemplate(
        SensorEntityDescription(
            key="inverter_state",
            translation_key="inverter_state",
            device_class=SensorDeviceClass.ENUM,
            options=["None", "Idle", "Focus", "UserCommand", "Dispatch"],
        ),
        value_fn=_data_field("inverter_state"),
    ),
    NemesisSensorTemplate(
        SensorEntityDescription(
            key="nemesis_state",
            translation_key="nemesis_state",
        ),
        value_fn=lambda d: (d.get("status") or {}).get("status"),
    ),
    NemesisSensorTemplate(
        SensorEntityDescription(
            key="machine_id",
            translation_key="machine_id",
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        value_fn=_short_machine_id,
    ),
    NemesisSensorTemplate(
        SensorEntityDescription(
            key="ip",
            translation_key="ip_address",
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        value_fn=lambda d: (d.get("status") or {}).get("ip"),
    ),
    NemesisSensorTemplate(
        SensorEntityDescription(
            key="unit_name",
            translation_key="unit_name",
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        value_fn=lambda d: _ctx(d).get("unit_name"),
    ),
    NemesisSensorTemplate(
        SensorEntityDescription(
            key="unit_id",
            translation_key="unit_id",
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        value_fn=lambda d: _ctx(d).get("unit_id"),
    ),
    NemesisSensorTemplate(
        SensorEntityDescription(
            key="version_short",
            translation_key="version_short",
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        value_fn=lambda d: (d.get("status") or {}).get("version_short")
        or (d.get("status") or {}).get("version"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: NemesisCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        NemesisSensor(coordinator, tpl.description, tpl.value_fn)
        for tpl in SENSOR_TEMPLATES
    )


class NemesisSensor(CoordinatorEntity[NemesisCoordinator], SensorEntity):
    """Sensor fed by the Nemesis coordinator."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: NemesisCoordinator,
        description: SensorEntityDescription,
        value_fn: Callable[[dict[str, Any]], StateType],
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._value_fn = value_fn
        uid = coordinator.config_entry.unique_id or coordinator.config_entry.entry_id
        self._attr_unique_id = f"{uid}-{description.key}"

    @property
    def native_value(self) -> StateType:
        return self._value_fn(self.coordinator.data)

    @property
    def device_info(self) -> DeviceInfo:
        status = self.coordinator.data.get("status") or {}
        machine_id = status.get("id") or self.coordinator.config_entry.unique_id
        ctx = status.get("context", {})
        unit_name = ctx.get("unit_name") if isinstance(ctx, dict) else None
        title = unit_name if isinstance(unit_name, str) and unit_name else "Nemesis"
        host = self.coordinator.config_entry.options.get(
            CONF_HOST, self.coordinator.config_entry.data[CONF_HOST]
        )
        port = int(
            self.coordinator.config_entry.options.get(
                CONF_PORT, self.coordinator.config_entry.data[CONF_PORT]
            )
        )
        base = http_base_url(host, port)
        return DeviceInfo(
            identifiers={(DOMAIN, str(machine_id))},
            name=title,
            manufacturer="Inowattio",
            model=str(status.get("version_long", "")),
            sw_version=str(status.get("version_short", status.get("version", ""))),
            configuration_url=f"{base}{ENDPOINT_STATUS}",
        )
