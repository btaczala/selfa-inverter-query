from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, CONF_EXPERT_MODE, WORKING_MODES
from .coordinator import SelfaCoordinator

WORKING_MODES_INV = {v: k for k, v in WORKING_MODES.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    if not entry.options.get(CONF_EXPERT_MODE, False):
        return

    coordinator: SelfaCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([SelfaWorkingModeSelect(coordinator)])


class SelfaWorkingModeSelect(CoordinatorEntity[SelfaCoordinator], SelectEntity):
    _attr_has_entity_name = True
    _attr_name = "Working Mode"
    _attr_options = list(WORKING_MODES.keys())

    def __init__(self, coordinator: SelfaCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_working_mode"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(identifiers={(DOMAIN, self.coordinator.serial_number)})

    @property
    def current_option(self) -> str | None:
        raw = self.coordinator.data.get("working_mode")
        return WORKING_MODES_INV.get(raw)

    async def async_select_option(self, option: str) -> None:
        value = WORKING_MODES[option]
        await self.coordinator.async_write_register(50000, value)
        await self.coordinator.async_request_refresh()
