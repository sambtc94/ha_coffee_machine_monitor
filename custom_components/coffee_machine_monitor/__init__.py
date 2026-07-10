from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN as DOMAIN
from .const import PLATFORMS
from .coordinator import CoffeeMachineMonitorCoordinator

type CoffeeMachineConfigEntry = ConfigEntry[CoffeeMachineMonitorCoordinator]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    return True


async def async_setup_entry(hass: HomeAssistant, entry: CoffeeMachineConfigEntry) -> bool:
    coordinator = CoffeeMachineMonitorCoordinator(hass, entry)
    await coordinator.async_setup()
    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: CoffeeMachineConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await entry.runtime_data.async_unload()
    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: CoffeeMachineConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
