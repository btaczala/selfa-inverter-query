import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback

from .const import DOMAIN, DEFAULT_HOST, DEFAULT_PORT, DEFAULT_SLAVE, CONF_EXPERT_MODE

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

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return SelfaOptionsFlow()


class SelfaOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input=None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        current = self.config_entry.options.get(CONF_EXPERT_MODE, False)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required(CONF_EXPERT_MODE, default=current): bool,
            }),
        )
