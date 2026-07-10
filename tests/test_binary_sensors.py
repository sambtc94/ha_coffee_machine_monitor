from __future__ import annotations


async def test_machine_on_stays_on_while_ready(
    set_source_state, setup_entry, get_entity_id, initialized_hass
):
    await set_source_state("0")
    entry = await setup_entry()
    state_entity = get_entity_id(entry.entry_id, "state")
    machine_on = get_entity_id(entry.entry_id, "machine_on", domain="binary_sensor")

    for value in (1469, 1491, 1462, 1505):
        await set_source_state(str(value), seconds=5)
    await set_source_state("3", seconds=5)

    assert initialized_hass.states.get(state_entity).state in {"ready", "finishing"}
    assert initialized_hass.states.get(machine_on).state == "on"


async def test_steaming_binary_sensor_tracks_steam_cycle(
    set_source_state, setup_entry, get_entity_id, initialized_hass
):
    await set_source_state("0")
    entry = await setup_entry()
    steam_entity = get_entity_id(entry.entry_id, "steaming_milk", domain="binary_sensor")

    for value in (1469, 1491, 1462, 1505, 1499):
        await set_source_state(str(value), seconds=5)
    await set_source_state("3", seconds=5)
    for value in (1509, 1218, 1225, 1226, 1519, 34, 18):
        await set_source_state(str(value), seconds=5)
    for value in (1467, 1466, 1470, 1463, 1462):
        await set_source_state(str(value), seconds=5)
    for value in (883, 882, 883):
        await set_source_state(str(value), seconds=5)

    assert initialized_hass.states.get(steam_entity).state == "on"
