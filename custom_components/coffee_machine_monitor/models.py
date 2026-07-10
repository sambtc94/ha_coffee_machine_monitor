from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from statistics import fmean, pstdev
from typing import Any

from .const import (
    DEFAULT_DIAGNOSTIC_ENTITIES,
    DEFAULT_THRESHOLD_OPTIONS,
    DEFAULT_TIMING_OPTIONS,
    DrinkType,
    MachineState,
    PowerPattern,
)


@dataclass(slots=True)
class ThresholdSettings:
    inactive_max_power: float = DEFAULT_THRESHOLD_OPTIONS["inactive_max_power"]
    active_min_power: float = DEFAULT_THRESHOLD_OPTIONS["active_min_power"]
    grinder_min_power: float = DEFAULT_THRESHOLD_OPTIONS["grinder_min_power"]
    grinder_max_power: float = DEFAULT_THRESHOLD_OPTIONS["grinder_max_power"]
    steam_min_power: float = DEFAULT_THRESHOLD_OPTIONS["steam_min_power"]
    steam_max_power: float = DEFAULT_THRESHOLD_OPTIONS["steam_max_power"]
    extraction_min_power: float = DEFAULT_THRESHOLD_OPTIONS["extraction_min_power"]
    heater_min_power: float = DEFAULT_THRESHOLD_OPTIONS["heater_min_power"]
    maximum_expected_power: float = DEFAULT_THRESHOLD_OPTIONS["maximum_expected_power"]

    @classmethod
    def from_mapping(cls, data: dict[str, Any] | None) -> ThresholdSettings:
        merged = {**DEFAULT_THRESHOLD_OPTIONS, **(data or {})}
        return cls(
            **{
                key: float(merged[key])
                for key in DEFAULT_THRESHOLD_OPTIONS
            }
        )

    def as_dict(self) -> dict[str, float]:
        return asdict(self)


@dataclass(slots=True)
class TimingSettings:
    startup_min_duration: int = DEFAULT_TIMING_OPTIONS["startup_min_duration"]
    grind_min_duration: int = DEFAULT_TIMING_OPTIONS["grind_min_duration"]
    extraction_min_duration: int = DEFAULT_TIMING_OPTIONS["extraction_min_duration"]
    steam_heat_min_duration: int = DEFAULT_TIMING_OPTIONS["steam_heat_min_duration"]
    steam_min_duration: int = DEFAULT_TIMING_OPTIONS["steam_min_duration"]
    rinse_max_duration: int = DEFAULT_TIMING_OPTIONS["rinse_max_duration"]
    activity_end_delay: int = DEFAULT_TIMING_OPTIONS["activity_end_delay"]
    low_power_gap_tolerance: int = DEFAULT_TIMING_OPTIONS["low_power_gap_tolerance"]
    session_end_delay: int = DEFAULT_TIMING_OPTIONS["session_end_delay"]
    unknown_timeout: int = DEFAULT_TIMING_OPTIONS["unknown_timeout"]
    minimum_valid_session_duration: int = DEFAULT_TIMING_OPTIONS["minimum_valid_session_duration"]

    @classmethod
    def from_mapping(cls, data: dict[str, Any] | None) -> TimingSettings:
        merged = {**DEFAULT_TIMING_OPTIONS, **(data or {})}
        return cls(
            **{
                key: int(merged[key])
                for key in DEFAULT_TIMING_OPTIONS
            }
        )

    def as_dict(self) -> dict[str, int]:
        return asdict(self)

    @property
    def startup_min(self) -> timedelta:
        return timedelta(seconds=self.startup_min_duration)

    @property
    def grind_min(self) -> timedelta:
        return timedelta(seconds=self.grind_min_duration)

    @property
    def extraction_min(self) -> timedelta:
        return timedelta(seconds=self.extraction_min_duration)

    @property
    def steam_heat_min(self) -> timedelta:
        return timedelta(seconds=self.steam_heat_min_duration)

    @property
    def steam_min(self) -> timedelta:
        return timedelta(seconds=self.steam_min_duration)

    @property
    def rinse_max(self) -> timedelta:
        return timedelta(seconds=self.rinse_max_duration)

    @property
    def activity_end(self) -> timedelta:
        return timedelta(seconds=self.activity_end_delay)

    @property
    def low_power_gap(self) -> timedelta:
        return timedelta(seconds=self.low_power_gap_tolerance)

    @property
    def session_end(self) -> timedelta:
        return timedelta(seconds=self.session_end_delay)

    @property
    def unknown(self) -> timedelta:
        return timedelta(seconds=self.unknown_timeout)

    @property
    def minimum_valid_session(self) -> timedelta:
        return timedelta(seconds=self.minimum_valid_session_duration)


@dataclass(slots=True)
class MonitorSettings:
    thresholds: ThresholdSettings = field(default_factory=ThresholdSettings)
    timings: TimingSettings = field(default_factory=TimingSettings)
    diagnostic_entities: bool = DEFAULT_DIAGNOSTIC_ENTITIES

    @classmethod
    def from_entry(cls, options: dict[str, Any], diagnostic_entities: bool) -> MonitorSettings:
        return cls(
            thresholds=ThresholdSettings.from_mapping(options),
            timings=TimingSettings.from_mapping(options),
            diagnostic_entities=diagnostic_entities,
        )


@dataclass(slots=True)
class PowerSample:
    timestamp: datetime
    power_w: float


@dataclass(slots=True)
class SampleStatistics:
    average: float = 0.0
    minimum: float = 0.0
    maximum: float = 0.0
    value_range: float = 0.0
    standard_deviation: float = 0.0
    samples: int = 0

    @classmethod
    def from_samples(cls, samples: list[PowerSample]) -> SampleStatistics:
        if not samples:
            return cls()
        values = [sample.power_w for sample in samples]
        minimum = min(values)
        maximum = max(values)
        return cls(
            average=round(fmean(values), 3),
            minimum=round(minimum, 3),
            maximum=round(maximum, 3),
            value_range=round(maximum - minimum, 3),
            standard_deviation=round(pstdev(values) if len(values) > 1 else 0.0, 3),
            samples=len(values),
        )


@dataclass(slots=True)
class ActivitySummary:
    activity: str
    start_time: datetime
    end_time: datetime
    duration_seconds: float
    average_power_w: float
    peak_power_w: float
    energy_kwh: float
    confidence: int
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "activity": self.activity,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "duration_seconds": round(self.duration_seconds, 3),
            "average_power_w": round(self.average_power_w, 3),
            "peak_power_w": round(self.peak_power_w, 3),
            "energy_kwh": round(self.energy_kwh, 6),
            "confidence": self.confidence,
            "reason": self.reason,
        }


@dataclass(slots=True)
class SessionSummary:
    start_time: datetime
    end_time: datetime | None = None
    duration_seconds: float = 0.0
    energy_kwh: float = 0.0
    peak_power: float = 0.0
    average_power: float = 0.0
    coffee_count: int = 0
    extraction_count: int = 0
    steam_cycle_count: int = 0
    rinse_count: int = 0
    contained_milk_steaming: bool = False
    activity_sequence: list[str] = field(default_factory=list)
    drink_type: str = DrinkType.UNKNOWN.value

    def as_dict(self) -> dict[str, Any]:
        return {
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": round(self.duration_seconds, 3),
            "energy_kwh": round(self.energy_kwh, 6),
            "peak_power": round(self.peak_power, 3),
            "average_power": round(self.average_power, 3),
            "coffee_count": self.coffee_count,
            "extraction_count": self.extraction_count,
            "steam_cycle_count": self.steam_cycle_count,
            "rinse_count": self.rinse_count,
            "contained_milk_steaming": self.contained_milk_steaming,
            "activity_sequence": list(self.activity_sequence),
            "drink_type": self.drink_type,
        }


@dataclass(slots=True)
class ActiveSession:
    start_time: datetime
    peak_power: float = 0.0
    energy_kwh: float = 0.0
    coffee_count: int = 0
    extraction_count: int = 0
    steam_cycle_count: int = 0
    rinse_count: int = 0
    contained_milk_steaming: bool = False
    activity_sequence: list[str] = field(default_factory=list)
    drink_type: str = DrinkType.UNKNOWN.value
    last_power_timestamp: datetime | None = None
    last_power_w: float | None = None
    low_power_started_at: datetime | None = None
    last_activity_at: datetime | None = None
    repeated_cycle_count: int = 0

    def as_summary(self, end_time: datetime) -> SessionSummary:
        duration_seconds = max((end_time - self.start_time).total_seconds(), 0.0)
        average_power = 0.0
        if duration_seconds > 0:
            average_power = (self.energy_kwh * 1000) / (duration_seconds / 3600)
        return SessionSummary(
            start_time=self.start_time,
            end_time=end_time,
            duration_seconds=duration_seconds,
            energy_kwh=self.energy_kwh,
            peak_power=self.peak_power,
            average_power=average_power,
            coffee_count=self.coffee_count,
            extraction_count=self.extraction_count,
            steam_cycle_count=self.steam_cycle_count,
            rinse_count=self.rinse_count,
            contained_milk_steaming=self.contained_milk_steaming,
            activity_sequence=list(self.activity_sequence),
            drink_type=self.drink_type,
        )


@dataclass(slots=True)
class MachineSnapshot:
    current_power_w: float | None = None
    source_available: bool = False
    source_value: str | None = None
    source_unit: str | None = None
    last_source_update: datetime | None = None
    state: str = MachineState.UNKNOWN.value
    previous_state: str = MachineState.UNKNOWN.value
    state_started_at: datetime | None = None
    state_duration_seconds: float = 0.0
    session_started_at: datetime | None = None
    reason: str = "Waiting for power samples"
    confidence: int = 0
    rolling_average_power: float = 0.0
    rolling_minimum_power: float = 0.0
    rolling_peak_power: float = 0.0
    rolling_range_power: float = 0.0
    rolling_standard_deviation: float = 0.0
    samples_in_window: int = 0
    current_activity_duration_seconds: float | None = None
    current_session_energy_kwh: float = 0.0
    last_session_energy_kwh: float | None = None
    coffees_today: int = 0
    total_coffees: int = 0
    milk_drinks_today: int = 0
    last_coffee_time: datetime | None = None
    last_activity: str = "none"
    last_coffee_duration_seconds: float | None = None
    last_steam_duration_seconds: float | None = None
    last_drink_type: str = DrinkType.UNKNOWN.value
    last_drink_confidence: int = 0
    power_pattern: str = PowerPattern.UNCLASSIFIED.value
    machine_on: bool = False
    current_session: SessionSummary | None = None
    last_session: SessionSummary | None = None
    entity_available: dict[str, bool] = field(default_factory=dict)

    def as_storage(self, local_day: date) -> dict[str, Any]:
        return {
            "coffees_today": self.coffees_today,
            "total_coffees": self.total_coffees,
            "milk_drinks_today": self.milk_drinks_today,
            "last_coffee_time": self.last_coffee_time.isoformat() if self.last_coffee_time else None,
            "last_activity": self.last_activity,
            "last_coffee_duration_seconds": self.last_coffee_duration_seconds,
            "last_steam_duration_seconds": self.last_steam_duration_seconds,
            "last_session_energy_kwh": self.last_session_energy_kwh,
            "last_drink_type": self.last_drink_type,
            "last_drink_confidence": self.last_drink_confidence,
            "daily_reset_date": local_day.isoformat(),
            "last_session": self.last_session.as_dict() if self.last_session else None,
        }


def restore_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def restore_session_summary(data: dict[str, Any] | None) -> SessionSummary | None:
    if not data:
        return None
    start_time = restore_datetime(data.get("start_time"))
    if start_time is None:
        return None
    summary = SessionSummary(
        start_time=start_time,
        end_time=restore_datetime(data.get("end_time")),
        duration_seconds=float(data.get("duration_seconds", 0.0)),
        energy_kwh=float(data.get("energy_kwh", 0.0)),
        peak_power=float(data.get("peak_power", 0.0)),
        average_power=float(data.get("average_power", 0.0)),
        coffee_count=int(data.get("coffee_count", 0)),
        extraction_count=int(data.get("extraction_count", 0)),
        steam_cycle_count=int(data.get("steam_cycle_count", 0)),
        rinse_count=int(data.get("rinse_count", 0)),
        contained_milk_steaming=bool(data.get("contained_milk_steaming", False)),
        activity_sequence=list(data.get("activity_sequence", [])),
        drink_type=str(data.get("drink_type", DrinkType.UNKNOWN.value)),
    )
    return summary
