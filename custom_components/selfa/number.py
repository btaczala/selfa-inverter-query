from dataclasses import dataclass

from homeassistant.components.number import NumberEntity, NumberEntityDescription, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

import dataclasses

from .const import DOMAIN, CONF_EXPERT_MODE, CONF_BREAKER, BREAKER_LIMITS
from .coordinator import SelfaCoordinator


@dataclass(frozen=True, kw_only=True)
class SelfaNumberDescription(NumberEntityDescription):
    register: int = 0
    # Converts a HA value (float) to the raw integer written to Modbus
    raw_from_value: object = None   # callable: value → int


NUMBERS: tuple[SelfaNumberDescription, ...] = (
    SelfaNumberDescription(
        key="battery_power_sched",
        name="Battery Power Scheduling",
        register=50207,
        native_min_value=-20.0,
        native_max_value=20.0,
        native_step=0.1,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        mode=NumberMode.BOX,
        raw_from_value=lambda v: int(v * 100) & 0xFFFF,
    ),
    SelfaNumberDescription(
        key="export_limit_value",
        name="Export Limit Value",
        register=25103,
        native_min_value=0.0,
        native_max_value=100.0,
        native_step=0.1,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        mode=NumberMode.BOX,
        raw_from_value=lambda v: int(v * 10),
    ),
    SelfaNumberDescription(
        key="import_limit_value",
        name="Import Limit Value",
        register=50009,
        native_min_value=0.0,
        native_max_value=100.0,
        native_step=0.1,
        native_unit_of_measurement="kVA",
        mode=NumberMode.BOX,
        raw_from_value=lambda v: int(v * 10),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    if not entry.options.get(CONF_EXPERT_MODE, False):
        return

    coordinator: SelfaCoordinator = hass.data[DOMAIN][entry.entry_id]
    breaker = entry.options.get(CONF_BREAKER, "16A")
    max_import = BREAKER_LIMITS.get(breaker, 11.0)

    entities = []
    for desc in NUMBERS:
        if desc.key == "import_limit_value":
            desc = dataclasses.replace(desc, native_max_value=max_import)
        entities.append(SelfaNumber(coordinator, desc))
    async_add_entities(entities)


class SelfaNumber(CoordinatorEntity[SelfaCoordinator], NumberEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: SelfaCoordinator, description: SelfaNumberDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.serial_number}_{description.key}"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(identifiers={(DOMAIN, self.coordinator.serial_number)})

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.get(self.entity_description.key)

    async def async_set_native_value(self, value: float) -> None:
        raw = self.entity_description.raw_from_value(value)
        await self.coordinator.async_write_register(self.entity_description.register, raw)
        await self.coordinator.async_request_refresh()
