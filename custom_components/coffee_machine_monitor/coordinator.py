from __future__ import annotations

import logging
from collections import deque
from collections.abc import Callable, Mapping
from datetime import date, datetime, timedelta
from itertools import pairwise
from statistics import fmean
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_NAME,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    ACTIVE_ACTIVITY_STATES,
    CLEANING_MIN_DURATION,
    CONF_DIAGNOSTIC_ENTITIES,
    CONF_SOURCE_ENTITY,
    DEFAULT_DEVICE_NAME,
    DEFAULT_TIMER_INTERVAL,
    DOMAIN,
    EVENT_ACTIVITY_FINISHED,
    EVENT_ACTIVITY_STARTED,
    EVENT_COFFEE_COMPLETED,
    EVENT_SESSION_FINISHED,
    EVENT_SESSION_STARTED,
    EVENT_STEAM_COMPLETED,
    SAMPLE_RETENTION,
    SESSION_ON_STATES,
    STORAGE_KEY,
    STORAGE_VERSION,
    SUPPORTED_UNITS,
    DrinkType,
    MachineState,
    PowerPattern,
)
from .models import (
    ActiveSession,
    ActivitySummary,
    MachineSnapshot,
    MonitorSettings,
    PowerSample,
    SampleStatistics,
    SessionSummary,
    restore_datetime,
    restore_session_summary,
)


class CoffeeMachineMonitorCoordinator(DataUpdateCoordinator[MachineSnapshot]):
    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            logger=logging.getLogger(__name__),
            name=DOMAIN,
            update_interval=None,
        )
        self.config_entry = entry
        self.source_entity = entry.data[CONF_SOURCE_ENTITY]
        self.device_name = entry.data.get(CONF_NAME, DEFAULT_DEVICE_NAME)
        self.settings = MonitorSettings.from_entry(
            entry.options,
            entry.data.get(CONF_DIAGNOSTIC_ENTITIES, False),
        )
        self.store: Store[dict[str, Any]] = Store(
            hass,
            STORAGE_VERSION,
            STORAGE_KEY.format(entry_id=entry.entry_id),
        )
        self._unsubscribers: list[Callable[[], None]] = []
        self._samples: deque[PowerSample] = deque()
        self._snapshot = MachineSnapshot()
        self._state: MachineState = MachineState.UNKNOWN
        self._previous_state: MachineState = MachineState.UNKNOWN
        self._state_started_at: datetime | None = None
        self._state_reason = "Waiting for power samples"
        self._state_confidence = 0
        self._source_available = False
        self._source_value: str | None = None
        self._source_unit: str | None = None
        self._current_power_w: float | None = None
        self._last_source_update: datetime | None = None
        self._last_valid_sample_at: datetime | None = None
        self._current_session: ActiveSession | None = None
        self._last_session: SessionSummary | None = None
        self._last_activity = "none"
        self._last_activity_finished_at: datetime | None = None
        self._last_coffee_time: datetime | None = None
        self._last_coffee_duration: float | None = None
        self._last_steam_duration: float | None = None
        self._last_session_energy: float | None = None
        self._last_extraction_completed_at: datetime | None = None
        self._grinding_seen_since_last_extraction = False
        self._coffees_today = 0
        self._total_coffees = 0
        self._milk_drinks_today = 0
        self._daily_reset_date: date | None = None
        self._last_drink_type = DrinkType.UNKNOWN.value
        self._last_drink_confidence = 0
        self._completed_activities: dict[MachineState, datetime] = {}
        self._activity_start: dict[MachineState, datetime] = {}
        self._suppress_events = False

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.config_entry.entry_id)},
            name=self.device_name,
            manufacturer="Virtual",
            model="Power Monitored Coffee Machine",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def listener_count(self) -> int:
        return len(self._unsubscribers)

    async def async_setup(self) -> None:
        await self._async_restore_storage_state()
        self._register_listeners()
        source_state = self.hass.states.get(self.source_entity)
        now = dt_util.utcnow()
        if source_state is not None:
            self._apply_source_state(source_state.state, source_state.attributes, now)
        self._evaluate(now)
        self.async_set_updated_data(self._build_snapshot(now))

    async def async_unload(self) -> None:
        while self._unsubscribers:
            self._unsubscribers.pop()()
        await self._async_save_state()

    def apply_restored_entity_state(self, key: str, value: str | None) -> None:
        if value is None:
            return
        if key == "coffees_today":
            self._coffees_today = max(self._coffees_today, int(float(value)))
        elif key == "total_coffees":
            self._total_coffees = max(self._total_coffees, int(float(value)))
        elif key == "milk_drinks_today":
            self._milk_drinks_today = max(self._milk_drinks_today, int(float(value)))
        elif key == "last_activity":
            self._last_activity = value
        elif key == "last_drink_type":
            self._last_drink_type = value

    def _register_listeners(self) -> None:
        self._unsubscribers.append(
            async_track_state_change_event(
                self.hass,
                [self.source_entity],
                self._async_source_state_changed,
            )
        )
        self._unsubscribers.append(
            async_track_time_interval(
                self.hass,
                self._async_periodic_refresh,
                DEFAULT_TIMER_INTERVAL,
            )
        )

    async def _async_restore_storage_state(self) -> None:
        stored = await self.store.async_load() or {}
        today = dt_util.as_local(dt_util.utcnow()).date()
        stored_day = stored.get("daily_reset_date")
        if stored_day == today.isoformat():
            self._coffees_today = int(stored.get("coffees_today", 0))
            self._milk_drinks_today = int(stored.get("milk_drinks_today", 0))
        self._daily_reset_date = today
        self._total_coffees = int(stored.get("total_coffees", 0))
        self._last_coffee_time = restore_datetime(stored.get("last_coffee_time"))
        self._last_activity = str(stored.get("last_activity", "none"))
        self._last_coffee_duration = self._coerce_float(stored.get("last_coffee_duration_seconds"))
        self._last_steam_duration = self._coerce_float(stored.get("last_steam_duration_seconds"))
        self._last_session_energy = self._coerce_float(stored.get("last_session_energy_kwh"))
        self._last_drink_type = str(stored.get("last_drink_type", DrinkType.UNKNOWN.value))
        self._last_drink_confidence = int(stored.get("last_drink_confidence", 0))
        self._last_session = restore_session_summary(stored.get("last_session"))

    async def _async_save_state(self) -> None:
        local_day = dt_util.as_local(dt_util.utcnow()).date()
        await self.store.async_save(self._build_snapshot(dt_util.utcnow()).as_storage(local_day))

    @callback
    def _async_source_state_changed(self, event: Event[EventStateChangedData]) -> None:
        new_state = event.data.get("new_state")
        now = dt_util.utcnow()
        if new_state is None:
            self._source_available = False
            self._source_value = None
            self._source_unit = None
            self._current_power_w = None
        else:
            self._apply_source_state(new_state.state, new_state.attributes, now)
        self._evaluate(now)
        self.async_set_updated_data(self._build_snapshot(now))
        self.hass.async_create_task(self._async_save_state())

    @callback
    def _async_periodic_refresh(self, now: datetime) -> None:
        self._evaluate(now)
        self.async_set_updated_data(self._build_snapshot(now))

    def _apply_source_state(
        self,
        state_value: str,
        attributes: Mapping[str, Any],
        now: datetime,
    ) -> None:
        self._last_source_update = now
        self._source_value = state_value
        self._source_unit = attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        power = self._normalize_power(state_value, self._source_unit)
        if power is None:
            self._source_available = False
            self._current_power_w = None
            return
        self._source_available = True
        self._current_power_w = power
        self._append_sample(now, power)
        self._update_session_energy(now, power)
        self._last_valid_sample_at = now

    def _append_sample(self, now: datetime, power: float) -> None:
        if self._samples and self._samples[-1].timestamp == now and self._samples[-1].power_w == power:
            return
        self._samples.append(PowerSample(now, power))
        cutoff = now - SAMPLE_RETENTION
        while self._samples and self._samples[0].timestamp < cutoff:
            self._samples.popleft()

    def _update_session_energy(self, now: datetime, power: float) -> None:
        if self._current_session is None:
            return
        previous_time = self._current_session.last_power_timestamp
        previous_power = self._current_session.last_power_w
        if previous_time is not None and previous_power is not None and now > previous_time:
            hours = (now - previous_time).total_seconds() / 3600
            self._current_session.energy_kwh += ((previous_power + power) / 2) / 1000 * hours
        self._current_session.last_power_timestamp = now
        self._current_session.last_power_w = power
        self._current_session.peak_power = max(self._current_session.peak_power, power)

    def _evaluate(self, now: datetime) -> None:
        self._reset_daily_counters(now)
        if self._last_source_update and now - self._last_source_update >= self.settings.timings.unknown:
            self._transition_to(MachineState.UNKNOWN, now, "Source sensor update timeout reached", 20)
            return
        if not self._source_available or self._current_power_w is None:
            if self._last_source_update is None or (
                self._last_source_update and now - self._last_source_update >= self.settings.timings.unknown
            ):
                self._transition_to(MachineState.UNKNOWN, now, "Source sensor is unavailable or invalid", 10)
            return

        current_power = self._current_power_w
        thresholds = self.settings.thresholds
        timings = self.settings.timings
        stats = self._rolling_statistics(now)
        pattern = self._detect_pattern(current_power, stats)
        recent_grinding = self._recent_activity({MachineState.GRINDING}, now, timedelta(minutes=2))
        recent_steam_activity = self._recent_activity(
            {MachineState.STEAM_HEATING, MachineState.STEAMING},
            now,
            timedelta(minutes=2),
        )
        session_age = now - self._current_session.start_time if self._current_session else timedelta(0)

        if self._current_session and current_power <= thresholds.inactive_max_power:
            if self._current_session.low_power_started_at is None:
                self._current_session.low_power_started_at = now
        elif self._current_session:
            self._current_session.low_power_started_at = None

        if self._current_session and self._current_session.last_activity_at:
            session_age = now - self._current_session.start_time
            if (
                session_age >= CLEANING_MIN_DURATION
                and self._current_session.extraction_count == 0
                and self._current_session.repeated_cycle_count >= 3
            ):
                self._transition_to(
                    MachineState.CLEANING,
                    now,
                    "Repeated heater and pump activity resembles a cleaning cycle",
                    82,
                )
                return

        if self._state == MachineState.STEAMING and current_power <= thresholds.inactive_max_power:
            gap = self._contiguous_duration(now, lambda value: value <= thresholds.inactive_max_power)
            if gap <= timings.low_power_gap:
                self._transition_to(
                    MachineState.STEAMING,
                    now,
                    "Temporary low-power gap retained as steaming",
                    88,
                )
                return

        if self._state == MachineState.EXTRACTING and current_power < thresholds.extraction_min_power:
            gap = self._contiguous_duration(now, lambda value: value < thresholds.extraction_min_power)
            if gap <= timings.activity_end:
                self._transition_to(
                    MachineState.EXTRACTING,
                    now,
                    "Variable extraction load retained through a short dip",
                    90,
                )
                return

        heater_duration = self._contiguous_duration(now, lambda value: value >= thresholds.heater_min_power)
        grind_duration = self._contiguous_duration(
            now,
            lambda value: thresholds.grinder_min_power <= value <= thresholds.grinder_max_power,
        )
        steam_duration = self._contiguous_duration(
            now,
            lambda value: thresholds.steam_min_power <= value <= thresholds.steam_max_power,
        )
        extraction_duration = self._contiguous_duration(now, lambda value: value >= thresholds.extraction_min_power)
        rinse_duration = self._contiguous_duration(now, lambda value: 700 <= value <= 1000)
        low_power_duration = self._contiguous_duration(now, lambda value: value <= thresholds.inactive_max_power)

        if heater_duration >= timings.startup_min and (
            self._current_session is None
            or (
                session_age <= timings.startup_min + timings.rinse_max + timedelta(seconds=10)
                and self._current_session.extraction_count == 0
                and self._current_session.steam_cycle_count == 0
                and not self._recent_activity(
                    {MachineState.GRINDING, MachineState.EXTRACTING, MachineState.STEAM_HEATING, MachineState.STEAMING},
                    now,
                    timedelta(minutes=5),
                )
            )
        ):
            self._ensure_session(now)
            self._transition_to(
                MachineState.STARTING,
                now,
                "Sustained heater load after inactive period",
                96,
            )
            return

        if (
            heater_duration >= timings.steam_heat_min
            and self._current_session is not None
            and self._state not in {MachineState.STARTING, MachineState.UNKNOWN}
            and self._recent_activity(
                {MachineState.EXTRACTING, MachineState.READY, MachineState.STEAMING},
                now,
                timedelta(minutes=3),
            )
        ):
            self._transition_to(
                MachineState.STEAM_HEATING,
                now,
                "Heater load during an active session following coffee activity",
                92,
            )
            return

        if (
            steam_duration >= timings.steam_min
            and self._current_session is not None
            and (
                self._recent_activity(
                    {MachineState.STEAM_HEATING, MachineState.EXTRACTING, MachineState.READY},
                    now,
                    timedelta(minutes=3),
                )
                or self._state == MachineState.STEAMING
            )
        ):
            self._transition_to(
                MachineState.STEAMING,
                now,
                f"Stable {round(current_power)} W load following steam heating",
                94,
            )
            return

        if (
            rinse_duration <= timings.rinse_max
            and 700 <= current_power <= 1000
            and not self._recent_activity({MachineState.STEAM_HEATING}, now, timedelta(minutes=2))
            and (
                self._recent_activity({MachineState.STARTING}, now, timedelta(seconds=45))
                or (
                    self._current_session is not None
                    and self._current_session.extraction_count == 0
                    and self._recent_activity(
                        {MachineState.READY, MachineState.HEATING, MachineState.FINISHING},
                        now,
                        timedelta(minutes=5),
                    )
                )
                or self._recent_activity({MachineState.EXTRACTING, MachineState.STEAMING}, now, timedelta(minutes=5))
            )
        ):
            self._ensure_session(now)
            self._transition_to(
                MachineState.RINSING,
                now,
                "Brief pump load classified as shutdown rinse",
                85,
            )
            return

        if (
            grind_duration >= timings.grind_min
            and self._state
            not in {MachineState.EXTRACTING, MachineState.STEAM_HEATING, MachineState.STEAMING}
            and not self._recent_activity({MachineState.STEAM_HEATING, MachineState.STEAMING}, now, timedelta(minutes=2))
            and not self._recent_activity({MachineState.STARTING}, now, timedelta(seconds=45))
            and (
                self._current_session is not None
                or self._recent_activity({MachineState.STARTING, MachineState.READY}, now, timedelta(minutes=5))
            )
        ):
            self._ensure_session(now)
            self._transition_to(
                MachineState.GRINDING,
                now,
                "Medium power band and recent heating resemble grinder activity",
                90,
            )
            return

        if (
            self._state not in {MachineState.STEAM_HEATING, MachineState.STEAMING}
            and not self._recent_activity({MachineState.STARTING}, now, timedelta(seconds=45))
            and (
                (
                    not recent_steam_activity
                    and session_age >= timings.startup_min
                    and extraction_duration >= timings.extraction_min
                )
                or (
                    current_power >= thresholds.active_min_power
                    and recent_grinding
                    and stats.value_range >= 200
                )
                or (
                    not recent_steam_activity
                    and session_age >= timings.startup_min
                    and current_power >= thresholds.active_min_power
                    and stats.average >= thresholds.extraction_min_power * 0.75
                    and stats.value_range >= 250
                )
            )
        ):
            self._ensure_session(now)
            self._transition_to(
                MachineState.EXTRACTING,
                now,
                "Variable high-power load following grinder activity",
                93 if recent_grinding else 78,
            )
            return

        if current_power >= thresholds.heater_min_power:
            self._ensure_session(now)
            self._transition_to(
                MachineState.HEATING,
                now,
                "Heater-level power without enough sequence context",
                65,
            )
            return

        if self._current_session is not None:
            if current_power <= thresholds.inactive_max_power:
                if low_power_duration >= timings.session_end:
                    self._finish_session(now)
                    self._transition_to(MachineState.OFF, now, "Low power persisted until session timeout elapsed", 97)
                    return
                ready_reason = "Low power retained as ready until session timeout"
                if self._state in ACTIVE_ACTIVITY_STATES:
                    self._transition_to(MachineState.FINISHING, now, "Waiting to determine whether another activity starts", 70)
                    return
                self._transition_to(MachineState.READY, now, ready_reason, 89)
                return

            if current_power < thresholds.active_min_power:
                self._transition_to(MachineState.READY, now, "Session is active with low idle power", 80)
                return

            self._transition_to(MachineState.READY, now, f"Power pattern {pattern.value} retained within active session", 60)
            return

        if current_power <= thresholds.inactive_max_power:
            self._transition_to(MachineState.OFF, now, "Power remained below the inactive threshold", 99)
            return

        self._ensure_session(now)
        self._transition_to(MachineState.HEATING, now, "Activity detected while previously off", 58)

    def _open_session(self, now: datetime) -> None:
        if self._current_session is not None:
            return
        self._current_session = ActiveSession(start_time=now)
        if self._current_power_w is not None:
            self._current_session.last_power_timestamp = now
            self._current_session.last_power_w = self._current_power_w
            self._current_session.peak_power = self._current_power_w
        if not self._suppress_events:
            self.hass.bus.async_fire(
                EVENT_SESSION_STARTED,
                {
                    "config_entry_id": self.config_entry.entry_id,
                    "device_name": self.device_name,
                    "start_time": now.isoformat(),
                },
            )

    def _ensure_session(self, now: datetime) -> None:
        if self._current_session is None:
            self._open_session(now)

    def _finish_session(self, now: datetime) -> None:
        if self._current_session is None:
            return
        summary = self._current_session.as_summary(now)
        summary.drink_type = self._classify_drink(summary)
        self._last_session = summary
        self._last_session_energy = round(summary.energy_kwh, 6)
        self._last_drink_type = summary.drink_type
        self._last_drink_confidence = 92 if summary.drink_type != DrinkType.UNKNOWN.value else 45
        if summary.extraction_count > 0 and summary.steam_cycle_count > 0:
            self._milk_drinks_today += 1
        if not self._suppress_events:
            self.hass.bus.async_fire(
                EVENT_SESSION_FINISHED,
                {
                    "config_entry_id": self.config_entry.entry_id,
                    "device_name": self.device_name,
                    "start_time": summary.start_time.isoformat(),
                    "end_time": summary.end_time.isoformat() if summary.end_time else None,
                    "duration_seconds": summary.duration_seconds,
                    "average_power_w": summary.average_power,
                    "peak_power_w": summary.peak_power,
                    "energy_kwh": summary.energy_kwh,
                    "coffee_number_today": self._coffees_today,
                    "total_coffees": self._total_coffees,
                    "drink_type": summary.drink_type,
                },
            )
        self._current_session = None

    def _transition_to(
        self,
        new_state: MachineState,
        now: datetime,
        reason: str,
        confidence: int,
    ) -> None:
        if self._state == new_state:
            self._state_reason = reason
            self._state_confidence = confidence
            if self._state_started_at is None:
                self._state_started_at = now
            return

        previous_state = self._state
        state_started_at = self._state_started_at or now
        if previous_state in ACTIVE_ACTIVITY_STATES:
            self._finish_activity(previous_state, state_started_at, now, self._state_reason, self._state_confidence)

        self._previous_state = previous_state
        self._state = new_state
        self._state_started_at = now
        self._state_reason = reason
        self._state_confidence = confidence

        if new_state in ACTIVE_ACTIVITY_STATES:
            self._start_activity(new_state, now)

    def _start_activity(self, state: MachineState, now: datetime) -> None:
        self._activity_start[state] = now
        if state == MachineState.GRINDING:
            self._grinding_seen_since_last_extraction = True
        if self._current_session is not None:
            if not self._current_session.activity_sequence or self._current_session.activity_sequence[-1] != state.value:
                self._current_session.activity_sequence.append(state.value)
            self._current_session.last_activity_at = now
            if state in {MachineState.RINSING, MachineState.HEATING, MachineState.STEAM_HEATING}:
                self._current_session.repeated_cycle_count += 1
        if not self._suppress_events:
            self.hass.bus.async_fire(
                EVENT_ACTIVITY_STARTED,
                {
                    "config_entry_id": self.config_entry.entry_id,
                    "device_name": self.device_name,
                    "activity": state.value,
                    "start_time": now.isoformat(),
                    "confidence": self._state_confidence,
                },
            )

    def _finish_activity(
        self,
        state: MachineState,
        start_time: datetime,
        end_time: datetime,
        reason: str,
        confidence: int,
    ) -> None:
        summary = self._summarize_activity(state, start_time, end_time, reason, confidence)
        self._completed_activities[state] = end_time
        self._last_activity = state.value
        self._last_activity_finished_at = end_time
        if self._current_session is not None:
            self._current_session.last_activity_at = end_time

        if (
            state == MachineState.EXTRACTING
            and summary.duration_seconds >= self.settings.timings.extraction_min_duration
            and self._should_count_extraction(end_time)
        ):
            self._coffees_today += 1
            self._total_coffees += 1
            self._last_coffee_time = end_time
            self._last_coffee_duration = summary.duration_seconds
            self._last_extraction_completed_at = end_time
            self._grinding_seen_since_last_extraction = False
            if self._current_session is not None:
                self._current_session.coffee_count += 1
                self._current_session.extraction_count += 1
            if not self._suppress_events:
                self.hass.bus.async_fire(
                    EVENT_COFFEE_COMPLETED,
                    {
                        "config_entry_id": self.config_entry.entry_id,
                        "device_name": self.device_name,
                        "activity": state.value,
                        "start_time": start_time.isoformat(),
                        "end_time": end_time.isoformat(),
                        "duration_seconds": summary.duration_seconds,
                        "average_power_w": summary.average_power_w,
                        "peak_power_w": summary.peak_power_w,
                        "energy_kwh": summary.energy_kwh,
                        "confidence": summary.confidence,
                        "coffee_number_today": self._coffees_today,
                        "total_coffees": self._total_coffees,
                        "drink_type": self._last_drink_type,
                    },
                )

        if state == MachineState.STEAMING and summary.duration_seconds >= self.settings.timings.steam_min_duration:
            self._last_steam_duration = summary.duration_seconds
            if self._current_session is not None:
                self._current_session.steam_cycle_count += 1
                self._current_session.contained_milk_steaming = True
            if not self._suppress_events:
                self.hass.bus.async_fire(
                    EVENT_STEAM_COMPLETED,
                    {
                        "config_entry_id": self.config_entry.entry_id,
                        "device_name": self.device_name,
                        "activity": state.value,
                        "start_time": start_time.isoformat(),
                        "end_time": end_time.isoformat(),
                        "duration_seconds": summary.duration_seconds,
                        "average_power_w": summary.average_power_w,
                        "peak_power_w": summary.peak_power_w,
                        "energy_kwh": summary.energy_kwh,
                        "confidence": summary.confidence,
                    },
                )

        if state == MachineState.RINSING and self._current_session is not None:
            self._current_session.rinse_count += 1

        if not self._suppress_events:
            self.hass.bus.async_fire(
                EVENT_ACTIVITY_FINISHED,
                {
                    "config_entry_id": self.config_entry.entry_id,
                    "device_name": self.device_name,
                    **summary.as_dict(),
                },
            )

    def _summarize_activity(
        self,
        state: MachineState,
        start_time: datetime,
        end_time: datetime,
        reason: str,
        confidence: int,
    ) -> ActivitySummary:
        samples = [
            sample for sample in self._samples if start_time <= sample.timestamp <= end_time
        ]
        values = [sample.power_w for sample in samples] or [self._current_power_w or 0.0]
        energy_kwh = 0.0
        for previous, current in pairwise(samples):
            if current.timestamp <= previous.timestamp:
                continue
            hours = (current.timestamp - previous.timestamp).total_seconds() / 3600
            energy_kwh += ((previous.power_w + current.power_w) / 2) / 1000 * hours
        return ActivitySummary(
            activity=state.value,
            start_time=start_time,
            end_time=end_time,
            duration_seconds=max((end_time - start_time).total_seconds(), 0.0),
            average_power_w=fmean(values),
            peak_power_w=max(values),
            energy_kwh=energy_kwh,
            confidence=confidence,
            reason=reason,
        )

    def _should_count_extraction(self, end_time: datetime) -> bool:
        if self._last_extraction_completed_at is None:
            return True
        if self._grinding_seen_since_last_extraction:
            return True
        return end_time - self._last_extraction_completed_at >= timedelta(minutes=2)

    def _rolling_statistics(self, now: datetime) -> SampleStatistics:
        samples = [sample for sample in self._samples if sample.timestamp >= now - timedelta(minutes=2)]
        return SampleStatistics.from_samples(samples)

    def _detect_pattern(self, power: float, stats: SampleStatistics) -> PowerPattern:
        thresholds = self.settings.thresholds
        if power <= thresholds.inactive_max_power:
            return PowerPattern.INACTIVE
        if power >= thresholds.heater_min_power:
            return PowerPattern.HEATER_LOAD
        if 700 <= power <= 1000 and stats.samples <= 4:
            return PowerPattern.PUMP_PULSE
        if thresholds.steam_min_power <= power <= thresholds.steam_max_power and stats.standard_deviation <= 160:
            return PowerPattern.STABLE_STEAM_LOAD
        if power >= thresholds.active_min_power and stats.value_range >= 250:
            return PowerPattern.VARIABLE_EXTRACTION_LOAD
        if power < thresholds.active_min_power:
            return PowerPattern.LOW_LOAD
        if power < thresholds.extraction_min_power:
            return PowerPattern.MEDIUM_LOAD
        return PowerPattern.UNCLASSIFIED

    def _contiguous_duration(self, now: datetime, predicate: Callable[[float], bool]) -> timedelta:
        if not self._samples:
            return timedelta(0)
        if not predicate(self._samples[-1].power_w):
            return timedelta(0)
        earliest = self._samples[-1].timestamp
        for sample in reversed(self._samples):
            if not predicate(sample.power_w):
                break
            earliest = sample.timestamp
        return max(now - earliest, timedelta(0))

    def _recent_activity(
        self,
        states: set[MachineState],
        now: datetime,
        duration: timedelta,
    ) -> bool:
        if self._state in states:
            return True
        for state in states:
            completed_at = self._completed_activities.get(state)
            if completed_at and now - completed_at <= duration:
                return True
        return False

    def _classify_drink(self, summary: SessionSummary) -> str:
        if summary.extraction_count > 1:
            return DrinkType.MULTIPLE_COFFEES.value
        if summary.extraction_count >= 1 and summary.steam_cycle_count >= 1:
            return DrinkType.MILK_COFFEE.value
        if summary.extraction_count >= 1:
            return DrinkType.BLACK_COFFEE.value
        if summary.rinse_count >= 2 or MachineState.CLEANING.value in summary.activity_sequence:
            return DrinkType.CLEANING_CYCLE.value
        if summary.activity_sequence:
            return DrinkType.HOT_WATER.value
        return DrinkType.UNKNOWN.value

    def _build_snapshot(self, now: datetime) -> MachineSnapshot:
        stats = self._rolling_statistics(now)
        current_session_summary = self._current_session.as_summary(now) if self._current_session else None
        if current_session_summary and self._current_session:
            current_session_summary.drink_type = self._classify_drink(current_session_summary)
        snapshot = MachineSnapshot(
            current_power_w=self._current_power_w,
            source_available=self._source_available,
            source_value=self._source_value,
            source_unit=self._source_unit,
            last_source_update=self._last_source_update,
            state=self._state.value,
            previous_state=self._previous_state.value,
            state_started_at=self._state_started_at,
            state_duration_seconds=(now - self._state_started_at).total_seconds() if self._state_started_at else 0.0,
            session_started_at=self._current_session.start_time if self._current_session else None,
            reason=self._state_reason,
            confidence=self._state_confidence,
            rolling_average_power=stats.average,
            rolling_minimum_power=stats.minimum,
            rolling_peak_power=stats.maximum,
            rolling_range_power=stats.value_range,
            rolling_standard_deviation=stats.standard_deviation,
            samples_in_window=stats.samples,
            current_activity_duration_seconds=(now - self._state_started_at).total_seconds()
            if self._state in ACTIVE_ACTIVITY_STATES and self._state_started_at
            else None,
            current_session_energy_kwh=round(self._current_session.energy_kwh, 6) if self._current_session else 0.0,
            last_session_energy_kwh=self._last_session_energy,
            coffees_today=self._coffees_today,
            total_coffees=self._total_coffees,
            milk_drinks_today=self._milk_drinks_today,
            last_coffee_time=self._last_coffee_time,
            last_activity=self._last_activity,
            last_coffee_duration_seconds=self._last_coffee_duration,
            last_steam_duration_seconds=self._last_steam_duration,
            last_drink_type=self._last_drink_type,
            last_drink_confidence=self._last_drink_confidence,
            power_pattern=self._detect_pattern(self._current_power_w or 0.0, stats).value,
            machine_on=self._current_session is not None or self._state in SESSION_ON_STATES,
            current_session=current_session_summary,
            last_session=self._last_session,
            entity_available={
                "power": self._source_available,
                "state": True,
                "detection_confidence": self._source_available or self._state == MachineState.UNKNOWN,
                "power_pattern": self._source_available,
            },
        )
        self._snapshot = snapshot
        return snapshot

    def _normalize_power(self, state_value: str, unit: str | None) -> float | None:
        if state_value in {STATE_UNKNOWN, STATE_UNAVAILABLE}:
            return None
        if unit not in SUPPORTED_UNITS:
            return None
        try:
            value = float(state_value)
        except (TypeError, ValueError):
            return None
        if unit == "kW":
            value *= 1000
        return round(value, 3)

    def _coerce_float(self, value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _reset_daily_counters(self, now: datetime) -> None:
        local_day = dt_util.as_local(now).date()
        if self._daily_reset_date is None:
            self._daily_reset_date = local_day
            return
        if self._daily_reset_date != local_day:
            self._coffees_today = 0
            self._milk_drinks_today = 0
            self._daily_reset_date = local_day

    def diagnostics(self) -> dict[str, Any]:
        now = dt_util.utcnow()
        snapshot = self._build_snapshot(now)
        return {
            "config": {
                "entry_id": self.config_entry.entry_id,
                "title": self.config_entry.title,
                "source_entity": self.source_entity,
                "diagnostic_entities": self.settings.diagnostic_entities,
            },
            "thresholds": self.settings.thresholds.as_dict(),
            "timings": self.settings.timings.as_dict(),
            "state_machine": {
                "state": snapshot.state,
                "previous_state": snapshot.previous_state,
                "reason": snapshot.reason,
                "confidence": snapshot.confidence,
                "state_started_at": snapshot.state_started_at.isoformat() if snapshot.state_started_at else None,
            },
            "recent_samples": {
                "count": snapshot.samples_in_window,
                "current_power_w": snapshot.current_power_w,
                "rolling_average_power": snapshot.rolling_average_power,
                "rolling_minimum_power": snapshot.rolling_minimum_power,
                "rolling_peak_power": snapshot.rolling_peak_power,
                "rolling_range_power": snapshot.rolling_range_power,
                "rolling_standard_deviation": snapshot.rolling_standard_deviation,
            },
            "current_session": snapshot.current_session.as_dict() if snapshot.current_session else None,
            "last_completed_session": snapshot.last_session.as_dict() if snapshot.last_session else None,
            "entity_availability": snapshot.entity_available,
            "source_sensor": {
                "unit": snapshot.source_unit,
                "status": "available" if snapshot.source_available else "unavailable",
                "last_source_update": snapshot.last_source_update.isoformat() if snapshot.last_source_update else None,
            },
        }
