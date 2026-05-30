#!/usr/bin/env python3
import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hardware.loadcell import LoadCell


def main():
    parser = argparse.ArgumentParser(description="Read HX711 values without tare/zero for wiring diagnostics.")
    parser.add_argument("--samples", type=int, default=60, help="Number of readings. Use 0 for endless.")
    parser.add_argument("--delay", type=float, default=0.25, help="Seconds between readings.")
    parser.add_argument("--average", type=int, default=1, help="HX711 samples per reading.")
    parser.add_argument("--reference-unit", type=float, default=1.0)
    parser.add_argument("--dout", type=int, default=5)
    parser.add_argument("--sck", type=int, default=6)
    args = parser.parse_args()

    load_cell = LoadCell(
        use_mock=False,
        dout_pin=args.dout,
        pd_sck_pin=args.sck,
        reference_unit=args.reference_unit,
        average_samples=args.average,
        filter_window=1,
    )

    print("Initializing HX711 without tare/zero...")
    load_cell._init_hardware()
    print(f"DOUT={load_cell.dout_pin} SCK={load_cell.pd_sck_pin} reference_unit={load_cell.reference_unit}")
    print("Pull or press on the load cell now. Ctrl+C stops.")
    print("index, reading, raw, error")

    count = 0
    try:
        while args.samples == 0 or count < args.samples:
            reading = load_cell.get_force()
            print(f"{count + 1}, {reading:.6f}, {load_cell.last_raw_lbs:.6f}, {load_cell.last_error}", flush=True)
            count += 1
            time.sleep(args.delay)
    except KeyboardInterrupt:
        print("Stopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
