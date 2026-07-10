from __future__ import annotations

from datetime import timedelta

from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed


async def test_setup_and_unload_entry(set_source_state, setup_entry, initialized_hass):
    await set_source_state("0")
    entry = await setup_entry()
    coordinator = entry.runtime_data

    assert coordinator.listener_count == 2
    assert entry.runtime_data.data.state == "off"

    assert await initialized_hass.config_entries.async_unload(entry.entry_id)
    await initialized_hass.async_block_till_done()

    assert coordinator.listener_count == 0


async def test_reload_does_not_duplicate_listeners_or_counts(
    set_source_state, setup_entry, initialized_hass, freezer
):
    await set_source_state("0")
    entry = await setup_entry()
    old_coordinator = entry.runtime_data

    for value in (1509, 1218, 1225, 1226, 1519):
        await set_source_state(str(value), seconds=5)
    await set_source_state("20", seconds=5)
    freezer.tick(timedelta(seconds=20))
    async_fire_time_changed(initialized_hass, dt_util.utcnow())
    await initialized_hass.async_block_till_done()

    assert entry.runtime_data.data.total_coffees == 1

    assert await initialized_hass.config_entries.async_reload(entry.entry_id)
    await initialized_hass.async_block_till_done()

    new_coordinator = entry.runtime_data
    assert old_coordinator.listener_count == 0
    assert new_coordinator.listener_count == 2
    assert new_coordinator.data.total_coffees == 1


async def test_restart_during_active_session_rebuilds_conservative_state(
    set_source_state, setup_entry
):
    await set_source_state("1450")
    entry = await setup_entry()

    assert entry.runtime_data.data.state in {"heating", "starting"}
    assert entry.runtime_data.data.total_coffees == 0
