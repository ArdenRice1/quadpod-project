#!/usr/bin/env python3
import argparse
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hardware.loadcell import LoadCell


def collect_counts(load_cell, samples, delay, label):
    values = []
    print(f"Collecting {samples} samples for {label}...")
    for index in range(samples):
        raw = load_cell._read_raw_counts()
        values.append(raw)
        print(f"  {index + 1:>3}: {raw:.3f}")
        time.sleep(delay)
    mean = statistics.mean(values)
    median = statistics.median(values)
    stdev = statistics.stdev(values) if len(values) > 1 else 0.0
    print(f"{label} mean={mean:.3f} median={median:.3f} stdev={stdev:.3f}")
    return values


def main():
    parser = argparse.ArgumentParser(description="Calibrate the Quadpod HX711/load cell using a known load.")
    parser.add_argument("--known-lbs", type=float, required=True, help="Known applied load in pounds.")
    parser.add_argument("--samples", type=int, default=25, help="Samples for unloaded and loaded readings.")
    parser.add_argument("--delay", type=float, default=0.1, help="Seconds between samples.")
    parser.add_argument("--dout", type=int, default=5, help="BCM GPIO connected to SparkFun DAT.")
    parser.add_argument("--sck", type=int, default=6, help="BCM GPIO connected to SparkFun CLK.")
    parser.add_argument("--old-reference-unit", type=float, default=1.0, help="Only used to initialize the reader.")
    args = parser.parse_args()

    if args.known_lbs == 0:
        raise SystemExit("--known-lbs must be non-zero")

    load_cell = LoadCell(
        use_mock=False,
        dout_pin=args.dout,
        pd_sck_pin=args.sck,
        reference_unit=args.old_reference_unit,
        average_samples=1,
        filter_window=1,
    )
    load_cell._init_hardware()

    print("Load cell calibration")
    print(f"DAT/DOUT=BCM {args.dout}, CLK/SCK=BCM {args.sck}, known load={args.known_lbs} lb")
    print("")
    input("Remove all load from the cell, keep it still, then press Enter...")
    zero_values = collect_counts(load_cell, args.samples, args.delay, "unloaded")
    zero = statistics.median(zero_values)

    print("")
    input(f"Apply the known {args.known_lbs} lb load, let it settle, then press Enter...")
    loaded_values = collect_counts(load_cell, args.samples, args.delay, "loaded")
    loaded = statistics.median(loaded_values)

    delta = loaded - zero
    reference_unit = delta / args.known_lbs
    sign_note = ""
    if reference_unit < 0:
        sign_note = "\nNote: reference unit is negative. That is usable, or swap WHITE/GREEN load-cell signal wires to make it positive."

    print("")
    print("Calibration result")
    print(f"unloaded_median_counts={zero:.3f}")
    print(f"loaded_median_counts={loaded:.3f}")
    print(f"delta_counts={delta:.3f}")
    print(f"known_lbs={args.known_lbs:.3f}")
    print(f"reference_unit={reference_unit:.6f}")
    print("")
    print("Use this before launching the app:")
    print(f"export QUADPOD_LOADCELL_REFERENCE_UNIT={reference_unit:.6f}")
    print(sign_note)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
