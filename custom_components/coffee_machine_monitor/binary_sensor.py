from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import BREW_ACTIVITY_STATES, STEAM_ACTIVITY_STATES, MachineState
from .coordinator import CoffeeMachineMonitorCoordinator

type BinaryValueFn = Callable[[CoffeeMachineMonitorCoordinator], bool]


@dataclass(frozen=True, kw_only=True)
class CoffeeMachineBinarySensorDescription(BinarySensorEntityDescription):
    value_fn: BinaryValueFn


DESCRIPTIONS: tuple[CoffeeMachineBinarySensorDescription, ...] = (
    CoffeeMachineBinarySensorDescription(
        key="active",
        translation_key="active",
        icon="mdi:toggle-switch",
        value_fn=lambda coordinator: coordinator.data.state
        in {
            MachineState.STARTING.value,
            MachineState.HEATING.value,
            MachineState.GRINDING.value,
            MachineState.EXTRACTING.value,
            MachineState.STEAM_HEATING.value,
            MachineState.STEAMING.value,
            MachineState.RINSING.value,
            MachineState.CLEANING.value,
        },
    ),
    CoffeeMachineBinarySensorDescription(
        key="making_coffee",
        translation_key="making_coffee",
        icon="mdi:coffee-maker-check",
        value_fn=lambda coordinator: coordinator.data.state
        in {state.value for state in BREW_ACTIVITY_STATES},
    ),
    CoffeeMachineBinarySensorDescription(
        key="extracting_coffee",
        translation_key="extracting_coffee",
        icon="mdi:coffee",
        value_fn=lambda coordinator: coordinator.data.state == MachineState.EXTRACTING.value,
    ),
    CoffeeMachineBinarySensorDescription(
        key="steaming_milk",
        translation_key="steaming_milk",
        icon="mdi:cup-water",
        value_fn=lambda coordinator: coordinator.data.state in {state.value for state in STEAM_ACTIVITY_STATES},
    ),
    CoffeeMachineBinarySensorDescription(
        key="machine_on",
        translation_key="machine_on",
        icon="mdi:power-plug",
        value_fn=lambda coordinator: coordinator.data.machine_on,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities,
) -> None:
    coordinator: CoffeeMachineMonitorCoordinator = entry.runtime_data
    async_add_entities(
        CoffeeMachineBinarySensor(coordinator, entry, description) for description in DESCRIPTIONS
    )


class CoffeeMachineBinarySensor(
    CoordinatorEntity[CoffeeMachineMonitorCoordinator], BinarySensorEntity
):
    entity_description: CoffeeMachineBinarySensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: CoffeeMachineMonitorCoordinator,
        entry: ConfigEntry,
        description: CoffeeMachineBinarySensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_translation_key = description.translation_key
        self._attr_device_info = coordinator.device_info

    @property
    def is_on(self) -> bool:
        return self.entity_description.value_fn(self.coordinator)
