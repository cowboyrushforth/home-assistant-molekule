from typing import Any, Dict, Optional
import voluptuous as vol
import logging
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from .const import DOMAIN, CONF_EMAIL, CONF_PASSWORD, CONF_REFRESH_RATE, CONF_REFRESH_RATE_DEFAULT, CONF_SILENT_AUTO
from .api import MolekuleApi

_LOGGER = logging.getLogger(__name__)

class ConfigFlowError(HomeAssistantError):
    """Base class for config flow errors."""

class AuthError(ConfigFlowError):
    """Authentication failed."""

class ApiError(ConfigFlowError):
    """API operation failed."""

class MolekuleConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1
    
    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        errors: Dict[str, str] = {}
        
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_EMAIL): str,
                        vol.Required(CONF_PASSWORD): str,
                    }
                ),
            )

        try:
            _LOGGER.debug("Attempting to authenticate with Molekule API")
            api = MolekuleApi(user_input[CONF_EMAIL], user_input[CONF_PASSWORD])
            
            try:
                await api.authenticate()
                _LOGGER.debug("Successfully authenticated with Molekule API")
            except Exception as auth_err:
                _LOGGER.error("Authentication failed with exception: %s", str(auth_err), exc_info=True)
                raise AuthError("Failed to authenticate") from auth_err
            
            try:
                # Test API connection by attempting to get devices
                devices = await api.get_devices()
                if devices is None:
                    _LOGGER.error("Failed to get devices after successful authentication")
                    raise ApiError("Failed to get devices")
                _LOGGER.debug("Successfully retrieved devices: %s", devices)
            except Exception as dev_err:
                _LOGGER.error("Failed to get devices: %s", str(dev_err), exc_info=True)
                raise ApiError("Failed to get device list") from dev_err
            finally:
                await api.close()

            # Check if this email is already configured
            await self.async_set_unique_id(user_input[CONF_EMAIL])
            
            # Instead of aborting, update existing entry if one exists
            existing_entry = await self.async_set_unique_id(user_input[CONF_EMAIL])
            if existing_entry:
                _LOGGER.debug("Updating existing configuration entry")
                self.hass.config_entries.async_update_entry(
                    existing_entry,
                    data=user_input,
                )
                # Let the user know we're updating instead of creating new
                return self.async_abort(reason="reauth_successful")

            # Create new entry if one doesn't exist
            return self.async_create_entry(
                title=user_input[CONF_EMAIL],
                data=user_input,
            )

        except AuthError:
            errors["base"] = "invalid_auth"
        except ApiError:
            errors["base"] = "cannot_connect"
        except Exception as ex:
            _LOGGER.exception("Unexpected exception occurred: %s", ex)
            errors["base"] = "unknown"

        # If we get here, there was an error
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
