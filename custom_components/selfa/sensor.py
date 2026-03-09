from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SENSORS
from .coordinator import SelfaCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: SelfaCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(SelfaSensor(coordinator, description) for description in SENSORS)


class SelfaSensor(CoordinatorEntity[SelfaCoordinator], SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: SelfaCoordinator, description) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.serial_number}_{description.key}"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.serial_number)},
            name="SELFA Inverter",
            manufacturer="SELFA",
            model="SFH Hybrid",
            sw_version=self.coordinator.firmware_version,
        )

    @property
    def native_value(self):
        value = self.coordinator.data.get(self.entity_description.key)
        if self.entity_description.value_map and value is not None:
            return self.entity_description.value_map.get(value, value)
        return value
