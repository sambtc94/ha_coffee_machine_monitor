from __future__ import annotations

from datetime import timedelta
from enum import StrEnum

from homeassistant.const import Platform

DOMAIN = "coffee_machine_monitor"
PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]

CONF_SOURCE_ENTITY = "source_entity"
CONF_DIAGNOSTIC_ENTITIES = "diagnostic_entities"

DEFAULT_DEVICE_NAME = "Coffee Machine"
DEFAULT_DIAGNOSTIC_ENTITIES = False

DEFAULT_THRESHOLD_OPTIONS: dict[str, float] = {
    "inactive_max_power": 5.0,
    "active_min_power": 300.0,
    "grinder_min_power": 500.0,
    "grinder_max_power": 1250.0,
    "steam_min_power": 800.0,
    "steam_max_power": 1200.0,
    "extraction_min_power": 1150.0,
    "heater_min_power": 1380.0,
    "maximum_expected_power": 1700.0,
}

DEFAULT_TIMING_OPTIONS: dict[str, int] = {
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
}

CLEANING_MIN_DURATION = timedelta(minutes=5)
SAMPLE_RETENTION = timedelta(minutes=10)
ROLLING_WINDOW = timedelta(minutes=2)
DEFAULT_TIMER_INTERVAL = timedelta(seconds=5)

STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}_{{entry_id}}"

EVENT_SESSION_STARTED = "coffee_machine_session_started"
EVENT_ACTIVITY_STARTED = "coffee_machine_activity_started"
EVENT_ACTIVITY_FINISHED = "coffee_machine_activity_finished"
EVENT_COFFEE_COMPLETED = "coffee_machine_coffee_completed"
EVENT_STEAM_COMPLETED = "coffee_machine_steam_completed"
EVENT_SESSION_FINISHED = "coffee_machine_session_finished"

SUPPORTED_UNITS = {"W", "kW"}


class MachineState(StrEnum):
    OFF = "off"
    STARTING = "starting"
    HEATING = "heating"
    READY = "ready"
    GRINDING = "grinding"
    EXTRACTING = "extracting"
    STEAM_HEATING = "steam_heating"
    STEAMING = "steaming"
    RINSING = "rinsing"
    CLEANING = "cleaning"
    FINISHING = "finishing"
    UNKNOWN = "unknown"


class DrinkType(StrEnum):
    ESPRESSO = "espresso"
    BLACK_COFFEE = "black_coffee"
    MILK_COFFEE = "milk_coffee"
    MULTIPLE_COFFEES = "multiple_coffees"
    HOT_WATER = "hot_water"
    CLEANING_CYCLE = "cleaning_cycle"
    UNKNOWN = "unknown"


class PowerPattern(StrEnum):
    INACTIVE = "inactive"
    LOW_LOAD = "low_load"
    MEDIUM_LOAD = "medium_load"
    HEATER_LOAD = "heater_load"
    STABLE_STEAM_LOAD = "stable_steam_load"
    VARIABLE_EXTRACTION_LOAD = "variable_extraction_load"
    PUMP_PULSE = "pump_pulse"
    UNCLASSIFIED = "unclassified"


PRIMARY_STATES = [state.value for state in MachineState]
DRINK_TYPES = [drink.value for drink in DrinkType]
POWER_PATTERNS = [pattern.value for pattern in PowerPattern]
ACTIVITY_OPTIONS = [
    MachineState.STARTING.value,
    MachineState.HEATING.value,
    MachineState.GRINDING.value,
    MachineState.EXTRACTING.value,
    MachineState.STEAM_HEATING.value,
    MachineState.STEAMING.value,
    MachineState.RINSING.value,
    MachineState.CLEANING.value,
    MachineState.FINISHING.value,
    "none",
]

ACTIVE_ACTIVITY_STATES = {
    MachineState.STARTING,
    MachineState.HEATING,
    MachineState.GRINDING,
    MachineState.EXTRACTING,
    MachineState.STEAM_HEATING,
    MachineState.STEAMING,
    MachineState.RINSING,
    MachineState.CLEANING,
}

BREW_ACTIVITY_STATES = {
    MachineState.GRINDING,
    MachineState.EXTRACTING,
}

STEAM_ACTIVITY_STATES = {
    MachineState.STEAM_HEATING,
    MachineState.STEAMING,
}

SESSION_ON_STATES = ACTIVE_ACTIVITY_STATES | {
    MachineState.READY,
    MachineState.FINISHING,
}

RESTORABLE_SENSOR_KEYS = {
    "coffees_today",
    "total_coffees",
    "milk_drinks_today",
    "last_coffee_time",
    "last_activity",
    "last_coffee_duration",
    "last_steam_duration",
    "last_session_energy",
    "last_drink_type",
}
