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
from homeassistant.const import EntityCategory
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


SENSOR_TEMPLATES: tuple[NemesisSensorTemplate, ...] = (
    NemesisSensorTemplate(
        SensorEntityDescription(
            key="grid_power",
            translation_key="grid_power",
            native_unit_of_measurement=UnitOfPower.WATT,
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_display_precision=0,
        ),
        value_fn=lambda d: (d.get("data") or {}).get("grid"),
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
        value_fn=lambda d: (d.get("status") or {}).get("id"),
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
            key="protocol",
            translation_key="protocol",
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        value_fn=lambda d: (d.get("status") or {}).get("protocol"),
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
        host = self.coordinator.config_entry.data[CONF_HOST]
        port = self.coordinator.config_entry.data[CONF_PORT]
        base = http_base_url(host, port)
        return DeviceInfo(
            identifiers={(DOMAIN, str(machine_id))},
            name=title,
            manufacturer="Inowattio",
            model=str(status.get("version_long", "")),
            sw_version=str(status.get("version_short", status.get("version", ""))),
            configuration_url=f"{base}{ENDPOINT_STATUS}",
        )
