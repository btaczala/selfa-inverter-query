from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN, CONF_BREAKER, BREAKER_LIMITS
from .coordinator import SelfaCoordinator

PLATFORMS = [Platform.SENSOR, Platform.SELECT, Platform.SWITCH, Platform.NUMBER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = SelfaCoordinator(
        hass,
        host=entry.data["host"],
        port=entry.data["port"],
        slave=entry.data["slave"],
    )
    breaker = entry.options.get(CONF_BREAKER, "16A")
    coordinator.breaker_type = breaker
    coordinator.max_import_kva = BREAKER_LIMITS.get(breaker, 11.0)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_on_options_change))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def _async_reload_on_options_change(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
