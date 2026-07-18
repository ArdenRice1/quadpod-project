# Audit backlog

Full reliability audit (2026-07-16, customer-readiness focus). Overarching theme: the
device must **fail safe** — never trust bad sensor data, never leave the actuator moving,
and never let "Stop" be overridden.

## Done

| Commit | Item |
|--------|------|
| `6cc11d4` | Replace glide hold with **settle-then-verify** seating (the reliability fix) |
| `17274b3` | Fail-safe defaults + over-tension gate + Stop hand-off guard (neutral 1650, anti-brick env parsing, ready-latch positive margin 1.25→0.15, hold aborts >1 lb, `/api/jog` 400 not 500) |
| `0597b39` | **P6** — test coverage for `_stop_reason_locked` safety envelope + glide hold |
| `b7d7002` | **P1a** — actuator watchdog: `stop()` retries I2C; `close()`/atexit force neutral on exit |
| `bcd200b` | **P1b** — load-cell liveness: flat-line (stuck/disconnected) detection stops Auto Tension |

## Remaining (in priority order)

### P4 — Calibration persistence + recency
Persist load-cell `reference_unit` + `zero_counts` (+ cal date) to
`flask_app/data/calibration.json`, load on boot → tare/calibration survive a restart
(removes the re-tare-every-restart friction). Gate rejects cal dates older than a
configurable window or in the future. Files: `hardware/loadcell.py`, `flask_app/engine.py`,
`config.py`, `flask_app/app.py` gate. Effort med, risk low-med.

### P2 — Actuator-owner / epoch refactor
Add `actuator_epoch`, bump on every ownership change (start_pull, jog, auto_preload start,
stop, hold start); each thread refuses to command (even neutral) if its epoch is stale.
Unify the two hold subsystems' lifecycle/cleanup. Closes the jog-stomp bug (a stale hold
thread neutralizing a fresh jog) and hardens the Stop hand-off. Files: `flask_app/engine.py`.
Effort high, risk high — de-risked now that P6 tests exist.

### P3 — Remove pulse mode → archive
Move `_auto_preload_pulse_loop` + support (staging/contact/coast/adaptive) to `archive/`.
Remove from `engine.py` + pulse-only config knobs + the legacy stage table if unused;
relocate pulse-only tests. Verify continuous + glide don't share removed helpers. Effort
high, risk med (dependency check). Requested by owner.

### P5 — Export data integrity
Unique export filenames (always include test/job id); atomic writes (temp + `os.replace`)
for CSV/ZIP/USB; CSV-injection guard (`=+-@`); DB schema migration (`PRAGMA user_version`);
retention/prune of exports + bound `force_samples` growth. Files: `flask_app/exporter.py`,
`flask_app/storage.py`. Effort med-high, risk low (off the control loop), high customer value.

### P7 — Network stranding UX
Validate Wi-Fi association before tearing down the hotspot; surface success/failure to the
phone; confirm the service has polkit/NOPASSWD for `nmcli`/`systemctl`. Files: `flask_app/app.py`,
`scripts/switch_network.py`, a status endpoint/template. Effort med, risk med.

### P8 — Lower priority
Serve via `waitress` (not the Werkzeug dev server); cache `/api/network/status` (drop the
~15 s of blocking `nmcli` off the request thread); skip `inject_globals` for `/api/*`.
(Email-queue robustness is moot — SMTP is intentionally disabled.)

## Loose ends
- Add `LOADCELL_LIVENESS_WINDOW` to `scripts/print_runtime_config.py` + `scripts/quadpod.env.example`.
- Continuous/pulse loops don't yet trip sensor-fault on `load_cell.last_error` (only glide does — fine while glide ships; wire in if pulse mode is kept).

## Owner decisions (from audit review)
True neutral = 1650µs. Over-tension >1 lb aborts (load cell is noisy — physics). Calibration
should enforce recency **and** persist. Asymmetric Victor envelope is correct. SMTP is
intentionally disabled. `SECRET_KEY` constant is acceptable for now. Pull requires a `test_id`
(already enforced). `jog("stop")` no-op during hold is correct (real Stop buttons use `/api/stop`).
