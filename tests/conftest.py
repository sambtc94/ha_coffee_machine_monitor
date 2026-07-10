from __future__ import annotations

import sys
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from custom_components.coffee_machine_monitor.const import (
    CONF_DIAGNOSTIC_ENTITIES,
    CONF_SOURCE_ENTITY,
    DOMAIN,
)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture
async def initialized_hass(hass: HomeAssistant) -> HomeAssistant:
    assert await async_setup_component(hass, "sensor", {})
    return hass


@pytest.fixture
def source_entity_id() -> str:
    return "sensor.espresso_machine_power"


@pytest.fixture
def set_source_state(initialized_hass: HomeAssistant, freezer, source_entity_id: str):
    async def _set_state(
        value: Any,
        *,
        unit: str = "W",
        seconds: int = 0,
        extra_attrs: dict[str, Any] | None = None,
    ) -> None:
        if seconds:
            freezer.tick(timedelta(seconds=seconds))
        attributes = {ATTR_UNIT_OF_MEASUREMENT: unit}
        if extra_attrs:
            attributes.update(extra_attrs)
        initialized_hass.states.async_set(source_entity_id, value, attributes)
        await initialized_hass.async_block_till_done()

    return _set_state


@pytest.fixture
async def setup_entry(initialized_hass: HomeAssistant, source_entity_id: str):
    async def _setup_entry(
        *,
        name: str = "Test Machine",
        diagnostic_entities: bool = True,
        options: dict[str, Any] | None = None,
    ) -> MockConfigEntry:
        entry = MockConfigEntry(
            domain=DOMAIN,
            title=name,
            data={
                "name": name,
                CONF_SOURCE_ENTITY: source_entity_id,
                CONF_DIAGNOSTIC_ENTITIES: diagnostic_entities,
            },
            options=options or {},
        )
        entry.add_to_hass(initialized_hass)
        assert await initialized_hass.config_entries.async_setup(entry.entry_id)
        await initialized_hass.async_block_till_done()
        return entry

    return _setup_entry


@pytest.fixture
def get_entity_id(initialized_hass: HomeAssistant):
    registry = er.async_get(initialized_hass)

    def _get(entry_id: str, key: str, domain: str = "sensor") -> str:
        entity_id = registry.async_get_entity_id(domain, DOMAIN, f"{entry_id}_{key}")
        assert entity_id is not None
        return entity_id

    return _get
