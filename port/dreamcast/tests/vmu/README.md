# Docked VMU tests

From this checkout on WSL/Linux:

```sh
python3 port/dreamcast/tests/vmu/run_tests.py
```

Requires Python 3 and a C++11 compiler (`CXX`, default `g++`). The test runner uses its own temporary build directory. No game assets, emulator or VMU are needed.

- `golden-docked.json` freezes the 25 supplied docked preview frames. Native output must match all 192 bytes.
- `render_cli.cpp` checks selector priority, health ownership, animation interruption and production ammo/health bounds. The fixture's percentage thresholds are for preview comparison only; production calls the recovered game's `getLifeLevel()`.
- `queue_test.cpp` checks latest-frame coalescing, retry/backoff, changed device identity, reconnect, timer wrap and save-derived story progression, suppression and removal.
- `platform_test.cpp` compiles the actual `game/platform/vmu_lcd.cpp` against the narrow fake KOS boundary in `stubs/`. It checks diagnostic leases, speed override, real controller-port selection, deterministic LCD slot choice, orientation call selection, throttling and reconnect animation cancellation.

These tests do not prove physical pixel orientation, asynchronous Maple delivery or console timing. Runtime evidence is recorded in `docs/VMU_IMPLEMENTATION_20261012.md`.
