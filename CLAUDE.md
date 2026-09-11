# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

FastAPI backend for a 5-DOF (rotating-table) laser cutter. It imports SVG designs, optimizes the cut path, generates FluidNC-flavored G-code, and streams it to the machine controller ("Corgi") over serial/WiFi with a WebSocket for live job control.

## Commands

Setup (uses [uv](https://github.com/astral-sh/uv) for deps, [ruff](https://docs.astral.sh/ruff/) for lint/format):
```sh
uv sync --group dev && uv run pre-commit install && cp .env.example .env
```

Run the server (docs at http://127.0.0.1:8000/docs):
```sh
uvicorn main:app --reload
```

Tests (pytest, rooted at repo root via `pythonpath = [""]` in pyproject.toml):
```sh
pytest                                  # all tests
pytest tests/local_optimizer            # one test dir
pytest tests/modules/test_greedy_optimizer.py::test_name  # single test
```

Lint/format (also runs via pre-commit on `ruff-check --fix` + `ruff-format`):
```sh
ruff check
ruff check --fix
ruff format
```

GCode sender utility (send a file directly to a machine at an address):
```sh
python3 -m util.send_gcode test.gcode 192.168.0.1:81
```

## Architecture

**Pipeline pattern.** `core/pipeline/base.py` defines `Module[TInput, TOutput]` (a typed `process()` step) and `Pipeline` (runs a list of modules in order, piping output to input). `core/pipeline/pipeline.py` assembles named pipelines from `FrontendInput`, e.g. `full_pipeline()`:
`SVG5DOF_Importer` → optional optimizer (`GreedyOptimizerModule` if `optimize=True`) → `GCodeExporter`.
Modules live under `core/modules/<name>/` and each wraps one pipeline stage (SVG import, path optimization, G-code export, visualization, nesting).

**Optimizers.** Several interchangeable path-optimization strategies (greedy, genetic, bucket, RPP-approximation, local, auto-nester) all extend `core/modules/base_optimizer.py`'s `BaseOptimizer(Module[Geometry, Geometry])`. Its `process()` is `@final`: it builds a kinematics cache from the geometry's cuts, calls the abstract `_optimize()`, then shifts the path to an optimal start configuration. Subclasses only implement `_optimize()` and `get_current_cost()`.

**Service container.** `core/service_container.py` has a single static `Container` class wiring up all services as class attributes (no DI framework/decorators despite the `Module` docstring mentioning `@inject`/`Provide` — that pattern isn't actually used). Services follow an interface/impl split in `core/services/`: an ABC (`XService`) plus an `XServiceImpl`, both registered in `Container`. Modules/optimizers reach services via `from core.service_container import Container; Container.kinematics_service...` rather than constructor injection.
- `LaserConfigService` reads machine geometry/kinematics/rates from `config.yaml` (a FluidNC-style board config — axes, kinematics, laser PWM settings for the "Corgi" board).
- `KinematicsService` wraps a **prebuilt native library** (`core/services/kinematics.so`, loaded via `ctypes`) that converts cartesian configurations to motor positions; no C source is checked in, so this `.so` must stay in sync with the C API defined in `kinematics_service.py` (`cartesian_to_closest_furthest_c`). It maintains a cache keyed by `Configuration` populated via `generate_cache()`.
- `LaserCostService` estimates travel cost between two `Configuration`s using Chebyshev distance over motor positions, `@cache`d.

**Core geometry model** (`core/models/geometry.py`): `Geometry` (collection of cuts + path-ordering logic), `Configuration` (cartesian x/y/alpha/beta laser head pose), `MotorPosition`, `TrapezoidalCut` (a single cut modeled as a depth-varying segment, exposing `configurations()` used to build the kinematics cache).

**API layer** (`api/`): `main.py`'s `app_factory()` wires routers, CORS, and a catch-all exception middleware that returns a `ResponseMessage` JSON error. Two entry points:
- `POST /generate_gcode` — runs `full_pipeline` synchronously and streams back a `.gcode` file.
- `POST /cut_svg` — builds the pipeline but defers execution, stashing it in the in-memory `jobs` dict (`api/routers/jobs.py`) keyed by a UUID `job_id`.
- `/ws/main` websocket (`api/routers/ws_router.py`) — on receiving a `{"type": "job_id", ...}` message, pops the job, runs its pipeline in a thread executor, then streams the resulting G-code to `CorgiInterface`. Also relays `abort`/`update` messages to the machine via a priority queue and pushes connection status back to the client via an outgoing queue.

**Machine interface** (`core/corgi_interface.py`): `CorgiInterface.main_loop()` runs on a background thread started from `main.py`'s FastAPI `lifespan`. It auto-detects a serial port (`ALLOW_WIFI_CONNECTION` is `False` by default — WiFi/`GCodeInterface` from the external `gcode-lib` package is a fallback path only), manages a send buffer against the controller's declared `buffer_size`, and drains/refills `incoming`/`outgoing` queues shared with the WebSocket router.

## Notes

- Pydantic request models use `StrictBaseModel` (`extra="forbid"`) in `api/models/base.py` — unknown fields in requests are rejected.
- `util/` holds standalone scripts (not part of the FastAPI app): G-code sending, laser power calibration, optimizer benchmarking/plotting (`util/optimizer/`), SVG path fixing.
- Naming conventions (from `tips.md`): `module_name`, `package_name`, `ClassName`, `method_name`, `ExceptionName`, `function_name`, `GLOBAL_CONSTANT_NAME`, `global_var_name`, `instance_var_name`, `function_parameter_name`, `local_var_name`.
