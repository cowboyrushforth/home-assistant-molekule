from typing import Any, Dict, Optional
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from .const import DOMAIN, CONF_EMAIL, CONF_PASSWORD, CONF_REFRESH_RATE, CONF_REFRESH_RATE_DEFAULT, CONF_SILENT_AUTO
from .api import MolekuleApi

class MolekuleConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        errors: Dict[str, str] = {}

        if user_input is not None:
            try:
                api = MolekuleApi(user_input[CONF_EMAIL], user_input[CONF_PASSWORD])
                await self.hass.async_add_executor_job(api.authenticate)
                await api.close()

                await self.async_set_unique_id(user_input[CONF_EMAIL])
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=user_input[CONF_EMAIL],
                    data=user_input,
                )
            except Exception:  # pylint: disable=broad-except
                errors["base"] = "auth"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_EMAIL): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return MolekuleOptionsFlow(config_entry)


class MolekuleOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        "sync_interval",
                        default=self.config_entry.options.get(CONF_REFRESH_RATE, CONF_REFRESH_RATE_DEFAULT),
                    ): int,
                    vol.Optional(
                        CONF_SILENT_AUTO,
                        default=self.config_entry.options.get(CONF_SILENT_AUTO, False),
                    ): bool,
                }
            ),
        )
