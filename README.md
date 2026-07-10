# ha_coffee_machine_monitor

A Home Assistant custom integration that watches an existing power sensor, mirrors it as a dedicated coffee-machine power entity, and infers coffee machine state, sessions, coffee counts, steaming, energy, and drink summaries.

## Proposed architecture

- **Config entry + options flow**: Select a source power sensor, machine name, and whether diagnostic entities are enabled.
- **Shared coordinator**: One event-driven coordinator per config entry listens to source sensor state changes, normalises power to watts, stores a rolling sample window, runs the sequence-aware state machine, tracks sessions, fires events, and persists counters.
- **Sensor platform**: Exposes mirrored power, state, counters, timestamps, durations, energy, drink classification, and optional diagnostics from coordinator snapshot data.
- **Binary sensor platform**: Exposes activity flags derived from the shared state machine.
- **Diagnostics**: Returns a redacted snapshot of current settings, state machine state, rolling statistics, and session summaries.
- **Persistence**: Lightweight storage keeps restorable counters and summary timestamps across restart without restoring transient activities.

## File tree

```text
custom_components/coffee_machine_monitor/
├── __init__.py
├── manifest.json
├── const.py
├── config_flow.py
├── coordinator.py
├── diagnostics.py
├── models.py
├── sensor.py
├── binary_sensor.py
├── services.yaml
├── strings.json
└── translations/
    └── en.json
tests/
├── conftest.py
├── test_binary_sensors.py
├── test_config_flow.py
├── test_init.py
├── test_options_flow.py
├── test_sensors.py
└── test_state_machine.py
```

## State-transition table

| From | Evidence | To |
| --- | --- | --- |
| off | Sustained heater load after inactivity | starting |
| off | Non-idle activity without enough startup context | heating |
| starting/ready | Medium grinder-band load for grind minimum duration | grinding |
| grinding/ready | Sustained or variable high-power brew pattern | extracting |
| ready/extracting | Sustained heater load later in active session | steam_heating |
| steam_heating/ready | Stable steam-band load, tolerant of short zero gaps | steaming |
| starting/ready/finishing | Brief pump-like load without brew evidence | rinsing |
| active states | Low power while waiting for follow-on activity | finishing |
| finishing/ready | Continued low power during active session | ready |
| ready | Session timeout after inactive power | off |
| any | Missing/invalid samples past unknown timeout | unknown |
| long mixed heater/pump session | Repeated rinse/heater pattern for cleaning duration | cleaning |

## Entity list

### Sensors

- Power
- State
- Coffees today
- Total coffees
- Milk drinks today
- Last coffee time
- Last activity
- Current activity duration
- Last coffee duration
- Last steam duration
- Current session energy
- Last session energy
- Last drink type
- Detection confidence *(optional diagnostic)*
- Power pattern *(optional diagnostic)*

### Binary sensors

- Active
- Making coffee
- Extracting coffee
- Steaming milk
- Machine on

## How the mirrored power sensor works

The integration listens for state changes on the selected Home Assistant source sensor instead of polling it. Each update is converted to watts (`kW × 1000` when needed), validated, and then exposed as a dedicated integration-owned sensor entity. That mirrored sensor belongs to the coffee machine device, always reports `W`, carries source metadata in attributes, and becomes unavailable immediately when the source state is unavailable, unknown, or non-numeric.

## Installation

### HACS custom repository

1. In HACS, open **Integrations**.
2. Choose **Custom repositories**.
3. Add `https://github.com/sambtc94/ha_coffee_machine_monitor` as an **Integration** repository.
4. Install **Coffee Machine Monitor**.
5. Restart Home Assistant.
6. Add the integration from **Settings → Devices & Services**.

### Manual install

1. Copy `custom_components/coffee_machine_monitor` into your Home Assistant `custom_components` directory.
2. Restart Home Assistant.
3. Add the integration from **Settings → Devices & Services**.

## Sample HACS repository structure

```text
ha_coffee_machine_monitor/
├── custom_components/
│   └── coffee_machine_monitor/
│       ├── __init__.py
│       ├── manifest.json
│       ├── ...
├── hacs.json
└── README.md
```

## Testing instructions

```bash
python -m pip install -e ".[dev]"
ruff check .
pytest
```

## Example dashboard YAML

```yaml
type: vertical-stack
cards:
  - type: entities
    title: Coffee Machine
    entities:
      - sensor.test_machine_power
      - sensor.test_machine_state
      - binary_sensor.test_machine_machine_on
      - sensor.test_machine_coffees_today
      - sensor.test_machine_total_coffees
      - sensor.test_machine_milk_drinks_today
      - sensor.test_machine_last_drink_type
      - sensor.test_machine_current_session_energy
  - type: gauge
    entity: sensor.test_machine_detection_confidence
    min: 0
    max: 100
```

## Example automation: announce completed coffee

```yaml
alias: Announce coffee completed
trigger:
  - platform: event
    event_type: coffee_machine_coffee_completed
action:
  - service: notify.mobile_app_phone
    data:
      message: >-
        {{ trigger.event.data.device_name }} finished a coffee.
        Drink type: {{ trigger.event.data.drink_type }}.
```

## Example automation: machine left on

```yaml
alias: Coffee machine left on
trigger:
  - platform: state
    entity_id: binary_sensor.test_machine_machine_on
    to: "on"
    for: "01:00:00"
condition:
  - condition: state
    entity_id: sensor.test_machine_state
    state: ready
action:
  - service: notify.mobile_app_phone
    data:
      message: Coffee machine has been ready for over an hour.
```

## Enable debug logging

```yaml
logger:
  logs:
    custom_components.coffee_machine_monitor: debug
```
