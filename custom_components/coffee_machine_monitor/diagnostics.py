from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import async_get as async_get_device_registry
from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry

from .coordinator import CoffeeMachineMonitorCoordinator


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    coordinator: CoffeeMachineMonitorCoordinator = entry.runtime_data
    diagnostics = coordinator.diagnostics()
    entity_registry = async_get_entity_registry(hass)
    device_registry = async_get_device_registry(hass)
    device = device_registry.async_get_device({(coordinator.config_entry.domain, coordinator.config_entry.entry_id)})
    diagnostics["registry"] = {
        "device_id": device.id if device else None,
        "entities": sorted(
            entity.entity_id
            for entity in entity_registry.entities.values()
            if entity.config_entry_id == entry.entry_id
        ),
    }
    return diagnostics
