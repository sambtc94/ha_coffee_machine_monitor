from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT, CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector

from .const import (
    CONF_DIAGNOSTIC_ENTITIES,
    CONF_SOURCE_ENTITY,
    DEFAULT_DEVICE_NAME,
    DEFAULT_DIAGNOSTIC_ENTITIES,
    DOMAIN,
    SUPPORTED_UNITS,
)
from .models import MonitorSettings


def _get_source_state_unit(hass: HomeAssistant, entity_id: str) -> str | None:
    state = hass.states.get(entity_id)
    if state is None:
        return None
    return state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)


class CoffeeMachineConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}

        if user_input is not None:
            source_entity = user_input[CONF_SOURCE_ENTITY]
            await self.async_set_unique_id(source_entity)
            self._abort_if_unique_id_configured()

            unit = _get_source_state_unit(self.hass, source_entity)
            if unit not in SUPPORTED_UNITS:
                errors[CONF_SOURCE_ENTITY] = "unsupported_unit"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data={
                        CONF_NAME: user_input[CONF_NAME],
                        CONF_SOURCE_ENTITY: source_entity,
                        CONF_DIAGNOSTIC_ENTITIES: user_input[CONF_DIAGNOSTIC_ENTITIES],
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SOURCE_ENTITY): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor", device_class="power")
                    ),
                    vol.Required(CONF_NAME, default=DEFAULT_DEVICE_NAME): str,
                    vol.Required(
                        CONF_DIAGNOSTIC_ENTITIES,
                        default=DEFAULT_DIAGNOSTIC_ENTITIES,
                    ): bool,
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return CoffeeMachineOptionsFlowHandler(config_entry)


class CoffeeMachineOptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry) -> None:
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        settings = MonitorSettings.from_entry(
            self.config_entry.options,
            self.config_entry.data.get(CONF_DIAGNOSTIC_ENTITIES, DEFAULT_DIAGNOSTIC_ENTITIES),
        )
        defaults: Mapping[str, Any] = {
            **settings.thresholds.as_dict(),
            **settings.timings.as_dict(),
        }

        schema = vol.Schema(
            {
                vol.Required(key, default=defaults[key]): vol.Coerce(float)
                for key in settings.thresholds.as_dict()
            }
            | {
                vol.Required(key, default=defaults[key]): vol.Coerce(int)
                for key in settings.timings.as_dict()
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
