# Contributing Guide

Thanks for your interest in Aria2c UI! Issues and PRs are welcome.

> 简体中文版见 [CONTRIBUTING.md](CONTRIBUTING.md)

## Development environment

```bash
# Windows 10/11, Python 3.10+
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt -r requirements-dev.txt

# Download aria2c (if not included in the repo)
# https://github.com/aria2/aria2/releases → put aria2c.exe into aria2c/

.venv\Scripts\python build.py dev    # run in dev mode
```

## Code layout at a glance

- `src/backend/main.py` — entry point: pywebview window, js_api (the frontend's single entry), state push thread
- `src/backend/aria2_client.py` — aria2 RPC client; errors are typed (`Aria2Error` / `Aria2Unavailable`)
- `src/backend/aria2_process.py` — aria2c process lifecycle (**platform-specific layer**)
- `src/backend/history.py` / `config.py` — user data persistence (**platform-agnostic**)
- `src/frontend/` — zero-dependency vanilla frontend; keyed updates prevent list flicker

## Commit conventions

- One PR, one concern; commit messages in Chinese or English, explaining the *why*
- Verify your change by actually running (`python build.py dev`); changes touching process management or sessions must be verified against real restart scenarios
- Do not introduce runtime network dependencies in the frontend (keep it offline); do not add HTTP servers

## Want to add Linux / macOS support?

Welcome! Platform-specific pieces are currently:

1. `aria2_process.py` — the Job Object (Windows-only) needs an equivalent per-platform process group management
2. Engine distribution — Linux/macOS users install aria2 themselves or fetch platform binaries
3. Packaging — PyInstaller onedir plus platform icon formats

Please open an issue to discuss the design before coding.

## Releasing a new version

CI auto-publishes releases (see [.github/workflows/release.yml](.github/workflows/release.yml)).
As a maintainer, just push a tag:

```bash
# 1. Update CHANGELOG.md and APP_VERSION in src/backend/main.py
# 2. Tag and push — Actions builds and publishes the Release automatically
git tag v1.x.0
git push origin v1.x.0
```

The workflow builds the onefile exe on a Windows runner, extracts the matching
section from CHANGELOG.md as release notes, and uploads `Aria2cUI.exe` to a
GitHub Release.
