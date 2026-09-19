import voluptuous as vol
from homeassistant import config_entries
from .const import DOMAIN, CONF_UPDATE_HOURS, DEFAULT_UPDATE_HOURS
class StreamingTopFrConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION=1
    async def async_step_user(self, user_input=None):
        if self._async_current_entries(): return self.async_abort(reason="single_instance_allowed")
        schema=vol.Schema({vol.Optional(CONF_UPDATE_HOURS, default=DEFAULT_UPDATE_HOURS): vol.All(vol.Coerce(int), vol.Range(min=2,max=24))})
        if user_input is not None: return self.async_create_entry(title="Streaming Top FR", data=user_input)
        return self.async_show_form(step_id="user", data_schema=schema)
