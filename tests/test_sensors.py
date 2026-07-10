from __future__ import annotations

from datetime import timedelta

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed


async def test_power_sensor_mirrors_watts(set_source_state, setup_entry, get_entity_id, initialized_hass):
    await set_source_state("450")
    entry = await setup_entry()
    entity_id = get_entity_id(entry.entry_id, "power")

    assert initialized_hass.states.get(entity_id).state == "450.0"


async def test_power_sensor_converts_kw(set_source_state, setup_entry, get_entity_id, initialized_hass):
    await set_source_state("1.45", unit="kW")
    entry = await setup_entry()
    entity_id = get_entity_id(entry.entry_id, "power")

    assert initialized_hass.states.get(entity_id).state == "1450.0"


async def test_power_sensor_becomes_unavailable(set_source_state, setup_entry, get_entity_id, initialized_hass):
    await set_source_state("450")
    entry = await setup_entry()
    entity_id = get_entity_id(entry.entry_id, "power")

    await set_source_state(STATE_UNAVAILABLE)

    assert initialized_hass.states.get(entity_id).state == STATE_UNAVAILABLE


async def test_session_energy_and_last_drink_type(
    set_source_state, setup_entry, get_entity_id, initialized_hass, freezer
):
    await set_source_state("0")
    entry = await setup_entry(options={"session_end_delay": 10})

    for value in (1469, 1491, 1462, 1505, 1499, 754, 38, 9, 1):
        await set_source_state(str(value), seconds=5)
    for value in (1053, 1215, 1165, 801, 584):
        await set_source_state(str(value), seconds=5)
    for value in (1509, 1218, 1225, 1226, 1519, 1518, 1226, 1354, 994, 34, 18):
        await set_source_state(str(value), seconds=5)
    for value in (1467, 1466, 1470, 1463, 1462):
        await set_source_state(str(value), seconds=5)
    for value in (883, 882, 883, 881, 0, 0, 886, 883, 1104, 1174, 880):
        await set_source_state(str(value), seconds=5)
    await set_source_state("0", seconds=5)
    freezer.tick(timedelta(seconds=20))
    async_fire_time_changed(initialized_hass, dt_util.utcnow())
    await initialized_hass.async_block_till_done()

    total_id = get_entity_id(entry.entry_id, "total_coffees")
    milk_id = get_entity_id(entry.entry_id, "milk_drinks_today")
    drink_type_id = get_entity_id(entry.entry_id, "last_drink_type")
    session_energy_id = get_entity_id(entry.entry_id, "last_session_energy")

    assert initialized_hass.states.get(total_id).state == "1"
    assert initialized_hass.states.get(milk_id).state == "1"
    assert initialized_hass.states.get(drink_type_id).state == "milk_coffee"
    assert float(initialized_hass.states.get(session_energy_id).state) > 0
