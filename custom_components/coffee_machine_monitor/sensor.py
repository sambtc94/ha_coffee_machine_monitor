from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfEnergy, UnitOfPower, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ACTIVITY_OPTIONS, DRINK_TYPES, POWER_PATTERNS, PRIMARY_STATES
from .coordinator import CoffeeMachineMonitorCoordinator
from .models import MachineSnapshot

type ValueFn = Callable[[MachineSnapshot], Any]
type AttrFn = Callable[[MachineSnapshot, CoffeeMachineMonitorCoordinator], dict[str, Any]]


@dataclass(frozen=True, kw_only=True)
class CoffeeMachineSensorDescription(SensorEntityDescription):
    value_fn: ValueFn
    attr_fn: AttrFn | None = None
    always_available: bool = False
    restore_state: bool = False
    diagnostic: bool = False


STATE_ICONS = {
    "off": "mdi:power",
    "starting": "mdi:coffee-maker",
    "heating": "mdi:water-boiler",
    "ready": "mdi:coffee-maker-check",
    "grinding": "mdi:grain",
    "extracting": "mdi:coffee",
    "steam_heating": "mdi:water-boiler-auto",
    "steaming": "mdi:cup-water",
    "rinsing": "mdi:waves",
    "cleaning": "mdi:spray-bottle",
    "finishing": "mdi:timer-sand",
    "unknown": "mdi:help-circle",
}


SENSOR_DESCRIPTIONS: tuple[CoffeeMachineSensorDescription, ...] = (
    CoffeeMachineSensorDescription(
        key="power",
        translation_key="power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:flash",
        value_fn=lambda snapshot: snapshot.current_power_w,
        attr_fn=lambda snapshot, coordinator: {
            "source_entity": coordinator.source_entity,
            "source_value": snapshot.source_value,
            "source_unit": snapshot.source_unit,
            "normalised_to_watts": True,
            "last_source_update": snapshot.last_source_update.isoformat() if snapshot.last_source_update else None,
        },
    ),
    CoffeeMachineSensorDescription(
        key="state",
        translation_key="state",
        device_class=SensorDeviceClass.ENUM,
        options=PRIMARY_STATES,
        value_fn=lambda snapshot: snapshot.state,
        attr_fn=lambda snapshot, coordinator: {
            "current_power": snapshot.current_power_w,
            "previous_state": snapshot.previous_state,
            "state_started_at": snapshot.state_started_at.isoformat() if snapshot.state_started_at else None,
            "state_duration": snapshot.state_duration_seconds,
            "session_started_at": snapshot.session_started_at.isoformat() if snapshot.session_started_at else None,
            "rolling_average_power": snapshot.rolling_average_power,
            "rolling_minimum_power": snapshot.rolling_minimum_power,
            "rolling_peak_power": snapshot.rolling_peak_power,
            "rolling_standard_deviation": snapshot.rolling_standard_deviation,
            "confidence": snapshot.confidence,
            "reason": snapshot.reason,
            "samples_in_window": snapshot.samples_in_window,
            "source_power_entity": coordinator.source_entity,
        },
        icon="mdi:coffee-maker-outline",
    ),
    CoffeeMachineSensorDescription(
        key="coffees_today",
        translation_key="coffees_today",
        icon="mdi:counter",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda snapshot: snapshot.coffees_today,
        restore_state=True,
        always_available=True,
    ),
    CoffeeMachineSensorDescription(
        key="total_coffees",
        translation_key="total_coffees",
        icon="mdi:coffee-outline",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda snapshot: snapshot.total_coffees,
        restore_state=True,
        always_available=True,
    ),
    CoffeeMachineSensorDescription(
        key="milk_drinks_today",
        translation_key="milk_drinks_today",
        icon="mdi:coffee-maker-check-outline",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda snapshot: snapshot.milk_drinks_today,
        restore_state=True,
        always_available=True,
    ),
    CoffeeMachineSensorDescription(
        key="last_coffee_time",
        translation_key="last_coffee_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda snapshot: snapshot.last_coffee_time,
        restore_state=True,
        always_available=True,
    ),
    CoffeeMachineSensorDescription(
        key="last_activity",
        translation_key="last_activity",
        device_class=SensorDeviceClass.ENUM,
        options=ACTIVITY_OPTIONS,
        value_fn=lambda snapshot: snapshot.last_activity,
        restore_state=True,
        always_available=True,
    ),
    CoffeeMachineSensorDescription(
        key="current_activity_duration",
        translation_key="current_activity_duration",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        icon="mdi:timer-outline",
        value_fn=lambda snapshot: round(snapshot.current_activity_duration_seconds)
        if snapshot.current_activity_duration_seconds is not None
        else None,
    ),
    CoffeeMachineSensorDescription(
        key="last_coffee_duration",
        translation_key="last_coffee_duration",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        icon="mdi:timer",
        value_fn=lambda snapshot: round(snapshot.last_coffee_duration_seconds)
        if snapshot.last_coffee_duration_seconds is not None
        else None,
        restore_state=True,
        always_available=True,
    ),
    CoffeeMachineSensorDescription(
        key="last_steam_duration",
        translation_key="last_steam_duration",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        icon="mdi:timer-cog-outline",
        value_fn=lambda snapshot: round(snapshot.last_steam_duration_seconds)
        if snapshot.last_steam_duration_seconds is not None
        else None,
        restore_state=True,
        always_available=True,
    ),
    CoffeeMachineSensorDescription(
        key="current_session_energy",
        translation_key="current_session_energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        icon="mdi:lightning-bolt",
        value_fn=lambda snapshot: round(snapshot.current_session_energy_kwh, 6),
    ),
    CoffeeMachineSensorDescription(
        key="last_session_energy",
        translation_key="last_session_energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        icon="mdi:battery-high",
        value_fn=lambda snapshot: snapshot.last_session_energy_kwh,
        restore_state=True,
        always_available=True,
    ),
    CoffeeMachineSensorDescription(
        key="last_drink_type",
        translation_key="last_drink_type",
        device_class=SensorDeviceClass.ENUM,
        options=DRINK_TYPES,
        icon="mdi:coffee-to-go-outline",
        value_fn=lambda snapshot: snapshot.last_drink_type,
        attr_fn=lambda snapshot, coordinator: {"confidence": snapshot.last_drink_confidence},
        restore_state=True,
        always_available=True,
    ),
    CoffeeMachineSensorDescription(
        key="detection_confidence",
        translation_key="detection_confidence",
        icon="mdi:gauge",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        diagnostic=True,
        value_fn=lambda snapshot: snapshot.confidence,
        attr_fn=lambda snapshot, coordinator: {
            "reason": snapshot.reason,
            "samples_in_window": snapshot.samples_in_window,
            "state": snapshot.state,
            "rolling_range_power": snapshot.rolling_range_power,
        },
    ),
    CoffeeMachineSensorDescription(
        key="power_pattern",
        translation_key="power_pattern",
        device_class=SensorDeviceClass.ENUM,
        options=POWER_PATTERNS,
        entity_category=EntityCategory.DIAGNOSTIC,
        diagnostic=True,
        value_fn=lambda snapshot: snapshot.power_pattern,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities,
) -> None:
    coordinator: CoffeeMachineMonitorCoordinator = entry.runtime_data
    entities: list[SensorEntity] = []
    for description in SENSOR_DESCRIPTIONS:
        if description.diagnostic and not coordinator.settings.diagnostic_entities:
            continue
        entity_cls = CoffeeMachineRestoreSensor if description.restore_state else CoffeeMachineSensor
        entities.append(entity_cls(coordinator, entry, description))
    async_add_entities(entities)


class CoffeeMachineSensor(CoordinatorEntity[CoffeeMachineMonitorCoordinator], SensorEntity):
    entity_description: CoffeeMachineSensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: CoffeeMachineMonitorCoordinator,
        entry: ConfigEntry,
        description: CoffeeMachineSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_translation_key = description.translation_key
        self._attr_device_info = coordinator.device_info

    @property
    def available(self) -> bool:
        if self.entity_description.always_available:
            return True
        return self.coordinator.data.entity_available.get(self.entity_description.key, self.coordinator.data.source_available)

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def icon(self) -> str | None:
        if self.entity_description.key == "state":
            return STATE_ICONS.get(self.coordinator.data.state, "mdi:coffee-maker")
        return self.entity_description.icon

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.attr_fn is None:
            return None
        return self.entity_description.attr_fn(self.coordinator.data, self.coordinator)


class CoffeeMachineRestoreSensor(CoffeeMachineSensor, RestoreEntity):
    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is None:
            return
        self.coordinator.apply_restored_entity_state(self.entity_description.key, last_state.state)
