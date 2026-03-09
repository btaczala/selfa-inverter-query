import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import DOMAIN, DEFAULT_HOST, DEFAULT_PORT, DEFAULT_SLAVE

STEP_SCHEMA = vol.Schema({
    vol.Required("host", default=DEFAULT_HOST): str,
    vol.Required("port", default=DEFAULT_PORT): int,
    vol.Required("slave", default=DEFAULT_SLAVE): int,
})


class SelfaConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="SELFA Inverter", data=user_input)

        return self.async_show_form(step_id="user", data_schema=STEP_SCHEMA)
