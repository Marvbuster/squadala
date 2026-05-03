# Repository Guidelines

## Project Structure & Module Organization

- `sidecar/`: Python 3.12 package `livegen` for FastAPI, LLM orchestration, schemas, layout solving, templates, and `.o2r` scene compilation.
- `sidecar/tests/`: pytest suite for API, schemas, solver behavior, and templates.
- `sidecar/src/livegen/templates/catalog/`: JSON room catalog data used by the sidecar.
- `tooling/`: Python scripts for extraction, test-scene generation, and binary/room experiments.
- `.wiki/`: primary knowledge base. Read `.wiki/INDEX.md` before implementation and add durable findings there.
- `docs/` and `release_notes/`: specs and versioned project notes.
- `roms/`, `_raw_data/`, `soh-source/`, and `SoH-App/`: local/reference assets; do not commit generated, copyrighted, or downloaded content.

## Build, Test, and Development Commands

Run sidecar commands from `sidecar/`:

```bash
uv sync
uv run pytest tests/ -v
uv run ruff check src/ tests/
uv run uvicorn livegen.api:app --reload --port 7777
```

- `uv sync`: install dependencies and dev tools.
- `uv run pytest tests/ -v`: run the sidecar test suite.
- `uv run ruff check src/ tests/`: validate imports, style, and naming.
- `uv run uvicorn ...`: start the FastAPI sidecar on `127.0.0.1:7777`.

Tooling tests can be run from the repository root, for example:

```bash
python -m pytest tooling/test_build_box_room.py -v
```

## Coding Style & Naming Conventions

Use Python 3.12 idioms, type hints for public interfaces, and English names in code. Ruff uses line length `99` and rules `E`, `F`, `I`, `N`, `UP`, and `RUF`; keep imports sorted. Prefer small modules under roughly 400 lines when practical. Documentation and release notes may be German; source code should remain English.

## Testing Guidelines

Tests use `pytest` and `pytest-asyncio` with `asyncio_mode = "auto"`. Place sidecar tests under `sidecar/tests/` and name files `test_*.py`. Cover schema validation, API behavior, solver constraints, and catalog/template changes. Add or update tests when changing contracts or generated output.

## Commit & Pull Request Guidelines

Recent commits use prefixes such as `feat:`, `docs:`, and `wip:` followed by a concise description, sometimes in German. Keep commits focused and mention the affected component when useful, for example `feat: add room template validation`.

Pull requests should include a summary, tests run, linked issue or milestone when applicable, and screenshots or logs for UI/gameplay changes. Do not include ROMs, `.env` files, downloaded SoH binaries, or generated artifacts.

## Agent-Specific Instructions

Before code changes, inspect `.wiki/INDEX.md`, `CLAUDE.md`, and the relevant source module. Do not edit upstream/reference SoH code in `soh-source/`; keep patches in owned sidecar, tooling, docs, or future livegen integration paths.
