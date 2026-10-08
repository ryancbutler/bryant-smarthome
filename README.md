# Bryant SmartHome CLI

A Python 3.10+ command-line client for reading Bryant SmartHome data and
previewing supported HVAC controls. Every command prints JSON to standard
output.

> **Independent project — not approved or endorsed by Bryant.** This software
> is not affiliated with, sponsored by, or supported by Bryant. Compatibility,
> available fields, accepted values, and operation availability can vary by
> account and equipment.

## HVAC features

### Inspect the system before changing it

Use `homes` to find each system serial, then use `system SERIAL` or
`zones SERIAL` to inspect the current system mode, outside temperature, zone
temperature and humidity, active setpoints, fan state, enabled zones, schedule
activity, manual activities, holds, and saved weekly program. `systems` also
reports Infinity connection status, model/firmware, diagnostics, and equipment
capabilities. These reads are the starting point for every control change.

### Set the system operating mode

`mode SERIAL VALUE` updates the system-wide Infinity operating mode. Supply a
value the device currently supports—for example, the mode shown by the system
itself—because the CLI does not guess accepted mode names or translate them.
The command previews the request first; append `--execute` to send it.

### Set manual heating and cooling temperatures

`temperature SERIAL ZONE --heat HEAT --cool COOL --fan FAN` saves a zone's
manual activity with both a heating and cooling setpoint. It is useful for
creating a manual heat/cool range or changing one side of the range while
preserving the other. The CLI requires both values, requires heat not to exceed
cool, and leaves the values in the thermostat's native temperature units.

This command changes the saved `manual` activity. The currently active zone
may still show a scheduled activity until the thermostat applies the manual
activity or a hold is in effect, so read the zone again afterward rather than
assuming the active setpoint changed immediately.

### Change zone fan behavior

`fan SERIAL ZONE VALUE --activity ACTIVITY` changes the fan setting for an
existing zone activity, such as its current manual or scheduled activity. Pass
the device's existing supported activity and fan values unchanged.

### Resume a scheduled program

`resume SERIAL ZONE` clears that zone's hold, returning it to its configured
schedule. This is the inverse of leaving a zone in a held manual state; verify
the current activity and hold fields after execution.

### Manage vacation settings

`vacation SERIAL --input-file PATH` enables Infinity vacation settings with
explicit start/end timestamps, heat/cool bounds, fan configuration, and
humidity settings. `vacation-cancel SERIAL` clears the vacation configuration.
The CLI validates the fields it understands but does not invent missing device
settings.

### Discover other supported equipment

For entry-level systems, `entry-system SERIAL` reads zones, comfort profiles,
and schedules. `device LOCATION_ID DEVICE_ID` reads consumer-device points and
desired configuration. `operations` lists other supported mutations, and
`mutate` can submit an explicit JSON input object when its server schema is
known to you. Raw mutations are advanced use only; being listed does not
establish that an operation is available for every account.

### Safe control workflow

Every HVAC control is a local preview until `--execute` is supplied. Review the
preview, obtain authorization, check live state immediately before execution,
and read the system afterward to confirm the persisted configuration. Failed
controls are never automatically replayed.

## Install and authenticate

Install the project for development:

```powershell
python -m pip install -e .
```

Copy the credential template, fill in your credentials, then discover systems:

```powershell
Copy-Item .env.example .env
bryant --non-interactive homes
```

The CLI reads only `BRYANT_USERNAME` and `BRYANT_PASSWORD`. Precedence is:
`--username`, then the process environment, then the dotenv file. The default
dotenv file is `.env` in the current directory; override it with `--env-file`.
Passwords are never printed or persisted. After password login, the CLI saves
the refresh token and short-lived access-token metadata in the OS credential
store, keyed by username; later commands refresh or reuse that session without
re-sending the password. Use `bryant logout` to remove it. `.env` is ignored by
Git; do not commit real credentials.

`bryant login` verifies credentials and saves a secure session. Without configured credentials it prompts
for an email/API username and hidden password; `--non-interactive` makes it
fail instead of prompting.

## Global options

Global options go before the command.

| Option | Argument | Meaning |
| --- | --- | --- |
| `--non-interactive` | none | Fail instead of prompting for missing credentials. Recommended for scripts and agents. |
| `--username USERNAME` | string | Username override. Takes precedence over `BRYANT_USERNAME`. |
| `--env-file PATH` | path | Dotenv file to load instead of `.env` in the working directory. |
| `--timeout SECONDS` | positive finite number | HTTP timeout; defaults to `30`. |

For example:

```powershell
bryant --non-interactive --env-file .env homes
```

## Read and discovery commands

These commands authenticate and perform read-only API requests.

| Command | Required arguments | What it returns |
| --- | --- | --- |
| `bryant login` | none | Verifies configured credentials and saves a secure session. |
| `bryant logout` | none | Removes the saved secure session for the configured username. |
| `bryant homes` | none | Locations, Infinity system serials, entry-level systems, and consumer devices. Use this first to find a system serial. |
| `bryant user` | none | User profile, location members, temperature-unit format, and systems. |
| `bryant systems` | none | Infinity systems, profiles, connection/mode status, diagnostics, and supported equipment. |
| `bryant system SERIAL` | `SERIAL` | One Infinity system's profile, status, zones, configuration, activities, and program. |
| `bryant zones SERIAL` | `SERIAL` | The status and configuration zone arrays from `system`. |
| `bryant entry-system SERIAL` | `SERIAL` | One entry-level system's zones, comfort profile, and schedule. |
| `bryant device LOCATION_ID DEVICE_ID` | `LOCATION_ID`, `DEVICE_ID` | Consumer-device points and desired configuration. IDs come from `homes`. |
| `bryant operations` | none | Supported mutation names and their input type names; this is offline discovery. |
| `bryant docs [TOPIC] [--format text\|json]` | optional command `TOPIC` | Offline CLI help. `TOPIC` must be a command name; `--format` defaults to `text`. |

`SERIAL`, zone IDs, `LOCATION_ID`, and `DEVICE_ID` are opaque device values:
pass them unchanged. Do not infer them from a model number or address.

## Control commands

Controls are **local previews by default**: they print the exact GraphQL
request body but do not authenticate or contact the equipment. Add `--execute`
only after reading current state, inspecting the preview, and obtaining
authorization to change the equipment. Check the system again afterward.

| Command | Required arguments | Optional arguments | Effect when executed |
| --- | --- | --- | --- |
| `bryant mode SERIAL VALUE` | `SERIAL`, `VALUE` | `--execute` | Sets the Infinity system mode to a device-supported value, passed unchanged. |
| `bryant temperature SERIAL ZONE --heat HEAT --cool COOL --fan FAN` | `SERIAL`, `ZONE`, finite `HEAT` and `COOL`, `FAN` | `--previous-fan VALUE`, `--execute` | Updates the zone's `manual` activity. Heat may not exceed cool; values use the device's native units and are not converted. |
| `bryant fan SERIAL ZONE VALUE --activity ACTIVITY` | `SERIAL`, `ZONE`, `VALUE`, `ACTIVITY` | `--execute` | Updates the fan value for the specified existing activity type. |
| `bryant resume SERIAL ZONE` | `SERIAL`, `ZONE` | `--execute` | Removes the zone hold and resumes its schedule. |
| `bryant vacation-cancel SERIAL` | `SERIAL` | `--execute` | Cancels Infinity vacation configuration. |
| `bryant vacation SERIAL --input-file PATH` | `SERIAL`, JSON `PATH` | `--execute` | Enables vacation configuration from an input object. |
| `bryant mutate OPERATION --input-file PATH` | supported `OPERATION`, JSON `PATH` | `--execute` | Sends a supported mutation using the supplied input object. |

`--execute` applies to every control command above. Failed control mutations
are not automatically replayed.

### Control input requirements

- `mode VALUE`, `fan VALUE`, `--fan FAN`, and `--activity ACTIVITY` must be
  existing values supported by that device. The CLI deliberately does not
  invent or translate accepted values.
- `temperature` requires both heat and cool values, even when only changing
  one; preserve the current value for the other setpoint. Both must be finite,
  and `HEAT` must be less than or equal to `COOL`.
- `--previous-fan` is optional and is passed as `previousFan` only when given.
- A vacation JSON object must contain `vacstart`, `vacend`, `vacfan`,
  `vacmint`, `vacmaxt`, and `humidityVacation`. Dates must be timezone-aware
  ISO 8601 timestamps with `vacend` after `vacstart`; temperatures must be
  finite with `vacmint <= vacmaxt`; `humidityVacation` must include
  `humidifier`, `rclg`, `rclgovercool`, and `rhtg`.
- A raw mutation input file must be a non-empty UTF-8 JSON object containing
  the mutation's input fields, not a GraphQL `variables` wrapper. Run
  `bryant operations` to list accepted operation names.

Examples:

```powershell
# Read state and discover the zone ID before changing anything.
bryant system SYSTEM_SERIAL
bryant zones SYSTEM_SERIAL

# Preview a mode change; no network request is made.
bryant mode SYSTEM_SERIAL cool

# Send it only after review and authorization.
bryant mode SYSTEM_SERIAL cool --execute

# Preview a manual Zone 1 setpoint update, retaining the existing heat value.
bryant temperature SYSTEM_SERIAL 1 --heat 70 --cool 75 --fan off
```

Run `bryant COMMAND --help` for parser-generated help for a specific command.

## License

This project is licensed under the [MIT License](LICENSE).

## Development

```powershell
python -m pip install -e .
python -m unittest discover -s tests -v
python -m compileall -q src tests
```

Tests are offline and do not contact an account or equipment.
