from dataclasses import dataclass

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, CONF_EXPERT_MODE
from .coordinator import SelfaCoordinator


@dataclass(frozen=True, kw_only=True)
class SelfaSwitchDescription(SwitchEntityDescription):
    register: int = 0


SWITCHES: tuple[SelfaSwitchDescription, ...] = (
    SelfaSwitchDescription(
        key="export_limit_enable",
        name="Export Limit",
        register=25100,
    ),
    SelfaSwitchDescription(
        key="import_limit_enable",
        name="Import Limit",
        register=50007,
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
    async_add_entities(SelfaSwitch(coordinator, desc) for desc in SWITCHES)


class SelfaSwitch(CoordinatorEntity[SelfaCoordinator], SwitchEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: SelfaCoordinator, description: SelfaSwitchDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.serial_number}_{description.key}"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(identifiers={(DOMAIN, self.coordinator.serial_number)})

    @property
    def is_on(self) -> bool | None:
        return self.coordinator.data.get(self.entity_description.key)

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.async_write_register(self.entity_description.register, 1)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_write_register(self.entity_description.register, 0)
        await self.coordinator.async_request_refresh()
