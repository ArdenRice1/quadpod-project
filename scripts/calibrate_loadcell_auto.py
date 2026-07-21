#!/usr/bin/env python3
"""Interactive load-cell calibration + verification for the Quadpod.

Static, multi-point calibration in the TENSION direction (same axis the pull
loads), which is the correct way to find counts-per-lb. The scale factor is a
fixed electro-mechanical property -- it does NOT change with movement type, so
calibrate sitting with known dead-weights, not during a pull.

Modes:
  calibrate  (default) tare -> read one or more known weights -> least-squares
             fit -> report linearity -> optionally auto-write the new
             reference_unit into /etc/quadpod.env and restart the service.
  verify     tare -> read known weight(s) -> report measured-vs-known error
             using the CURRENT reference_unit, without changing anything.

Run on the Pi (it stops/starts the quadpod service itself so it can own the
load-cell GPIO):
    python3 /opt/quadpod/scripts/calibrate_loadcell_auto.py
    python3 /opt/quadpod/scripts/calibrate_loadcell_auto.py --mode verify
"""
import argparse
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from hardware.loadcell import LoadCell, save_calibration_record  # noqa: E402

ENV_PATH = "/etc/quadpod.env"
ENV_KEY = "QUADPOD_LOADCELL_REFERENCE_UNIT"
SERVICE = "quadpod"


def sh(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def read_env():
    """Return {key: value} parsed from /etc/quadpod.env (via sudo)."""
    r = sh(["sudo", "-n", "cat", ENV_PATH])
    env = {}
    if r.returncode == 0:
        for line in r.stdout.splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env, (r.stdout if r.returncode == 0 else None)


def write_reference_unit(current_text, value):
    """Rewrite (or append) the reference-unit line and persist via sudo tee."""
    lines = current_text.splitlines()
    out, replaced = [], False
    for line in lines:
        if line.strip().startswith(ENV_KEY + "="):
            out.append(f"{ENV_KEY}={value}")
            replaced = True
        else:
            out.append(line)
    if not replaced:
        out.append(f"{ENV_KEY}={value}")
    payload = "\n".join(out) + "\n"
    p = subprocess.run(["sudo", "-n", "tee", ENV_PATH], input=payload,
                       capture_output=True, text=True)
    return p.returncode == 0


def collect(load_cell, samples, delay, label):
    vals = []
    print(f"  reading {label} ({samples} samples)...", end="", flush=True)
    for _ in range(samples):
        vals.append(load_cell._read_raw_counts())
        time.sleep(delay)
    med = statistics.median(vals)
    sd = statistics.pstdev(vals)
    print(f" median={med:.1f} counts  noise(std)={sd:.1f} counts (~{sd/max(1,abs(med) or 1):.4f})")
    return med, sd


def ask_weights(prompt):
    print(prompt)
    weights = []
    while True:
        raw = input(f"  known weight #{len(weights)+1} in lb (blank to finish): ").strip()
        if not raw:
            break
        try:
            w = float(raw)
            if w == 0:
                print("  must be non-zero"); continue
            weights.append(w)
        except ValueError:
            print("  not a number")
    return weights


def main():
    ap = argparse.ArgumentParser(description="Quadpod load-cell calibration/verification")
    ap.add_argument("--mode", choices=["calibrate", "verify"], default="calibrate")
    ap.add_argument("--samples", type=int, default=30)
    ap.add_argument("--delay", type=float, default=0.05)
    ap.add_argument("--dout", type=int, default=5)
    ap.add_argument("--sck", type=int, default=6)
    ap.add_argument("--no-service", action="store_true", help="do not stop/start the service")
    ap.add_argument("--no-persist", action="store_true", help="calibrate but do not write env")
    args = ap.parse_args()

    env, env_text = read_env()
    cur_ref = float(env.get(ENV_KEY, "1") or "1")
    print(f"Quadpod load-cell {args.mode.upper()}")
    print(f"current {ENV_KEY} = {cur_ref}\n")

    stopped = False
    if not args.no_service:
        print(f"stopping {SERVICE} service to take the load cell...")
        if sh(["sudo", "-n", "systemctl", "stop", SERVICE]).returncode == 0:
            stopped = True
            time.sleep(1.0)

    lc = LoadCell(use_mock=False, dout_pin=args.dout, pd_sck_pin=args.sck,
                  reference_unit=cur_ref, average_samples=1, filter_window=1)
    try:
        lc._init_hardware()
        input("Remove ALL load, let it settle, then press Enter to TARE...")
        zero, zsd = collect(lc, args.samples, args.delay, "unloaded (zero)")

        weights = ask_weights("\nApply known weights one at a time in the TENSION direction "
                              "(same way the pull loads it).")
        if not weights:
            print("no weights entered; nothing to do."); return 0

        points = []  # (known_lbs, delta_counts)
        for w in weights:
            input(f"\nApply {w} lb, let it settle, then press Enter...")
            loaded, lsd = collect(lc, args.samples, args.delay, f"loaded {w} lb")
            points.append((w, loaded - zero))

        # least-squares slope through origin: counts = ref * lbs
        num = sum(d * w for w, d in points)
        den = sum(w * w for w, _ in points)
        ref = num / den if den else float("nan")

        print("\n" + "=" * 56)
        print(f"{'known_lb':>9} {'delta_counts':>13} {'implied_ref':>12} {'pred_lb':>9} {'err_lb':>8} {'err%':>7}")
        max_err_pct = 0.0
        for w, d in points:
            implied = d / w
            pred = d / ref if ref else float("nan")
            err = pred - w
            errp = 100 * err / w
            max_err_pct = max(max_err_pct, abs(errp))
            print(f"{w:>9.2f} {d:>13.1f} {implied:>12.1f} {pred:>9.3f} {err:>+8.3f} {errp:>+6.2f}%")
        print("=" * 56)
        print(f"zero_counts={zero:.1f}  noise≈{zsd:.1f} counts (~{zsd/abs(ref) if ref else 0:.4f} lb)")
        print(f"NEW reference_unit = {ref:.4f}   (was {cur_ref})")
        print(f"worst point error = {max_err_pct:.2f}%  -> {'GOOD, linear' if max_err_pct < 2 else 'CHECK: nonlinear/off-axis or bad weight'}")
        if ref < 0:
            print("note: reference_unit is negative (usable). Swap load-cell WHITE/GREEN to flip sign if desired.")

        if args.mode == "verify":
            print("\nverify mode: no changes written.")
            return 0
        if args.no_persist:
            print(f"\n--no-persist: set it yourself -> {ENV_KEY}={ref:.4f}")
            return 0
        if env_text is None:
            print("\ncould not read env (sudo). Set manually: "
                  f"{ENV_KEY}={ref:.4f}")
            return 1
        ans = input(f"\nWrite {ENV_KEY}={ref:.4f} to {ENV_PATH}? [y/N] ").strip().lower()
        if ans == "y":
            if write_reference_unit(env_text, f"{ref:.4f}"):
                print("written.")
                record = save_calibration_record(ref, "bench-script")
                print(f"provenance recorded: calibrated_at={record.get('calibrated_at')}")
            else:
                print("FAILED to write env (sudo).")
        else:
            print("not written.")
        return 0
    finally:
        try:
            lc.gpio and lc.gpio.cleanup()
        except Exception:
            pass
        if stopped:
            print(f"restarting {SERVICE}...")
            sh(["sudo", "-n", "systemctl", "start", SERVICE])


if __name__ == "__main__":
    raise SystemExit(main())
