from __future__ import annotations

from datetime import timedelta

from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed


async def test_startup_rinse_does_not_increment_coffee_count(
    set_source_state, setup_entry, get_entity_id, initialized_hass
):
    await set_source_state("0")
    entry = await setup_entry()
    state_entity = get_entity_id(entry.entry_id, "state")
    count_entity = get_entity_id(entry.entry_id, "total_coffees")

    for value in (1469, 1491, 1462, 1505, 1499, 754, 38, 9, 1):
        await set_source_state(str(value), seconds=5)

    assert initialized_hass.states.get(state_entity).state in {"ready", "finishing"}
    assert initialized_hass.states.get(count_entity).state == "0"


async def test_grinding_followed_by_extraction_counts_once(
    set_source_state, setup_entry, get_entity_id, initialized_hass, freezer
):
    await set_source_state("0")
    entry = await setup_entry()
    state_entity = get_entity_id(entry.entry_id, "state")
    count_entity = get_entity_id(entry.entry_id, "total_coffees")

    for value in (1053, 1215, 1165, 801, 584):
        await set_source_state(str(value), seconds=5)
    assert initialized_hass.states.get(state_entity).state == "grinding"

    for value in (1509, 1218, 1225, 1226, 1519, 1518, 1226, 1354, 994, 34, 18):
        await set_source_state(str(value), seconds=5)
    freezer.tick(timedelta(seconds=20))
    async_fire_time_changed(initialized_hass, dt_util.utcnow())
    await initialized_hass.async_block_till_done()

    assert initialized_hass.states.get(count_entity).state == "1"


async def test_extraction_without_recognised_grind(set_source_state, setup_entry):
    await set_source_state("0")
    entry = await setup_entry()

    for value in (1509, 1218, 1225, 1226, 1519):
        await set_source_state(str(value), seconds=5)

    assert entry.runtime_data.data.state == "extracting"


async def test_temporary_zero_readings_do_not_end_steaming_early(set_source_state, setup_entry):
    await set_source_state("0")
    entry = await setup_entry()

    for value in (1467, 1466, 1470, 1463, 1462):
        await set_source_state(str(value), seconds=5)
    for value in (883, 882, 883, 881, 0, 0, 886, 883, 1104, 1174, 880):
        await set_source_state(str(value), seconds=5)

    assert entry.runtime_data.data.state == "steaming"


async def test_shutdown_rinse_detection(set_source_state, setup_entry):
    await set_source_state("0")
    entry = await setup_entry()

    for value in (1469, 1491, 1462, 1505):
        await set_source_state(str(value), seconds=5)
    await set_source_state("3", seconds=5)
    await set_source_state("905", seconds=5)

    assert entry.runtime_data.data.state == "rinsing"
    assert entry.runtime_data.data.total_coffees == 0


async def test_ready_transitions_to_off_after_timeout(
    set_source_state, setup_entry, initialized_hass, freezer
):
    await set_source_state("0")
    entry = await setup_entry(options={"session_end_delay": 10})

    for value in (1469, 1491, 1462, 1505):
        await set_source_state(str(value), seconds=5)
    await set_source_state("3", seconds=5)

    freezer.tick(timedelta(seconds=20))
    async_fire_time_changed(initialized_hass, dt_util.utcnow())
    await initialized_hass.async_block_till_done()

    assert entry.runtime_data.data.state == "off"


async def test_source_unavailable_goes_unknown_and_recovers(
    set_source_state, setup_entry, initialized_hass, freezer
):
    await set_source_state("0")
    entry = await setup_entry()

    await set_source_state("unavailable")
    freezer.tick(timedelta(minutes=4))
    async_fire_time_changed(initialized_hass, dt_util.utcnow())
    await initialized_hass.async_block_till_done()

    assert entry.runtime_data.data.state == "unknown"

    await set_source_state("1450")

    assert entry.runtime_data.data.state in {"heating", "starting"}


async def test_duplicate_timestamps_are_tolerated(set_source_state, setup_entry, freezer):
    await set_source_state("0")
    entry = await setup_entry()

    await set_source_state("1450")
    await set_source_state("1450")

    assert entry.runtime_data.data.current_power_w == 1450.0


async def test_irregular_sampling_is_supported(set_source_state, setup_entry):
    await set_source_state("0")
    entry = await setup_entry()

    await set_source_state("1450", seconds=5)
    await set_source_state("1450", seconds=10)
    await set_source_state("1450", seconds=7)

    assert entry.runtime_data.data.state in {"starting", "heating"}


async def test_coffees_today_resets_at_midnight(
    set_source_state, setup_entry, initialized_hass, freezer, get_entity_id
):
    await set_source_state("0")
    entry = await setup_entry()
    count_entity = get_entity_id(entry.entry_id, "coffees_today")
    total_entity = get_entity_id(entry.entry_id, "total_coffees")

    for value in (1509, 1218, 1225, 1226, 1519, 34):
        await set_source_state(str(value), seconds=5)
    freezer.tick(timedelta(seconds=20))
    async_fire_time_changed(initialized_hass, dt_util.utcnow())
    await initialized_hass.async_block_till_done()
    assert initialized_hass.states.get(count_entity).state == "1"

    freezer.move_to("2026-07-11 00:01:00+00:00")
    async_fire_time_changed(initialized_hass, dt_util.utcnow())
    await initialized_hass.async_block_till_done()

    assert initialized_hass.states.get(count_entity).state == "0"
    assert initialized_hass.states.get(total_entity).state == "1"


async def test_cleaning_cycle_detection(set_source_state, setup_entry, initialized_hass, freezer):
    await set_source_state("0")
    entry = await setup_entry()

    for _ in range(4):
        for value in (1460, 1462, 900, 20):
            await set_source_state(str(value), seconds=45)

    assert entry.runtime_data.data.state == "cleaning"
