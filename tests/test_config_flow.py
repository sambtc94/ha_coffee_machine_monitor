from __future__ import annotations

from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.coffee_machine_monitor.const import (
    CONF_DIAGNOSTIC_ENTITIES,
    CONF_SOURCE_ENTITY,
    DOMAIN,
)


async def test_config_flow_accepts_watt_sensor(hass):
    hass.states.async_set("sensor.machine_power", "450", {ATTR_UNIT_OF_MEASUREMENT: "W"})

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_SOURCE_ENTITY: "sensor.machine_power",
            "name": "Kitchen Machine",
            CONF_DIAGNOSTIC_ENTITIES: True,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Kitchen Machine"


async def test_config_flow_accepts_kw_sensor(hass):
    hass.states.async_set("sensor.machine_power", "1.45", {ATTR_UNIT_OF_MEASUREMENT: "kW"})

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_SOURCE_ENTITY: "sensor.machine_power",
            "name": "Kitchen Machine",
            CONF_DIAGNOSTIC_ENTITIES: False,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_config_flow_rejects_unsupported_units(hass):
    hass.states.async_set("sensor.machine_power", "4", {ATTR_UNIT_OF_MEASUREMENT: "A"})

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_SOURCE_ENTITY: "sensor.machine_power",
            "name": "Kitchen Machine",
            CONF_DIAGNOSTIC_ENTITIES: False,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_SOURCE_ENTITY: "unsupported_unit"}


async def test_config_flow_prevents_duplicate_configuration(hass):
    hass.states.async_set("sensor.machine_power", "400", {ATTR_UNIT_OF_MEASUREMENT: "W"})
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SOURCE_ENTITY: "sensor.machine_power",
            "name": "Machine",
            CONF_DIAGNOSTIC_ENTITIES: False,
        },
        unique_id="sensor.machine_power",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_SOURCE_ENTITY: "sensor.machine_power",
            "name": "Kitchen Machine",
            CONF_DIAGNOSTIC_ENTITIES: False,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
