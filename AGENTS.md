# Repository guidance

## Purpose and layout

This project provides a Python CLI for Bryant HVAC. Python 3.10 or later is
required. Install for development with `python -m pip install -e .`; the command
is `bryant`.

- `src/bryant_smarthome/cli.py`: argument parsing, JSON output, credential
  selection, and preview/execute controls.
- `src/bryant_smarthome/client.py`: HTTP transport and sanitized API errors.
- `src/bryant_smarthome/auth.py`: password, refresh, and social authentication.
- `src/bryant_smarthome/config.py`: dotenv loading and environment precedence.
- `src/bryant_smarthome/operations.py`: GraphQL operation definitions.
- `tests/`: offline unittest coverage, including mocked transport integration.
- `README.md`: installation and user-facing command documentation.

## API behavior

Keep new CLI behavior and its documentation consistent. Do not infer accepted
values, temperature conversions, complete schemas, or production availability
without verification.

## Credentials and equipment

Never print or commit passwords or tokens. Avoid reading private `.env` files
unless required by the task; use `.env.example` for configuration documentation.
Keep private dotenv files ignored. Process environment variables take precedence
over dotenv values; explicit `--username` overrides both.

Preserve OS credential-store persistence and sanitized errors. All control
commands must preview locally by default and require `--execute` to mutate.
Never automatically replay failed mutations. Reads may refresh and retry once
after an authentication failure.

Before changing real HVAC equipment, obtain explicit user authorization for the
change, check current state immediately before execution, and verify persisted
state afterward. Offline development checks do not require live credentials.

## Verification

Run these checks after code changes:

```powershell
python -m unittest discover -s tests -v
python -m compileall -q src tests
```

Use mocked credentials and transports in tests. Add regression coverage when
changing authentication, request behavior, argument validation, or mutation
guards. Do not treat passing offline tests as live API verification.

## Working tree

Preserve existing local work, including untracked files. Do not commit, publish,
or perform live account actions unless requested.
