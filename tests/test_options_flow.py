from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant.data_entry_flow import FlowResultType


async def test_options_flow_updates_entry_and_reloads(set_source_state, setup_entry, initialized_hass):
    await set_source_state("0")
    entry = await setup_entry(diagnostic_entities=False)

    with patch.object(initialized_hass.config_entries, "async_reload", AsyncMock()) as mock_reload:
        result = await initialized_hass.config_entries.options.async_init(entry.entry_id)
        result = await initialized_hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                "inactive_max_power": 4,
                "active_min_power": 250,
                "grinder_min_power": 500,
                "grinder_max_power": 1250,
                "steam_min_power": 800,
                "steam_max_power": 1200,
                "extraction_min_power": 1150,
                "heater_min_power": 1380,
                "maximum_expected_power": 1700,
                "startup_min_duration": 15,
                "grind_min_duration": 10,
                "extraction_min_duration": 15,
                "steam_heat_min_duration": 15,
                "steam_min_duration": 10,
                "rinse_max_duration": 20,
                "activity_end_delay": 12,
                "low_power_gap_tolerance": 15,
                "session_end_delay": 600,
                "unknown_timeout": 180,
                "minimum_valid_session_duration": 30,
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options["inactive_max_power"] == 4
    mock_reload.assert_awaited_once_with(entry.entry_id)
