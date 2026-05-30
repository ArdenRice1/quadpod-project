#!/usr/bin/env python3
import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hardware.loadcell import LoadCell


def main():
    parser = argparse.ArgumentParser(description="Read the HX711/load cell without starting the web app.")
    parser.add_argument("--samples", type=int, default=60, help="Number of readings to print. Use 0 for endless.")
    parser.add_argument("--delay", type=float, default=0.25, help="Seconds between readings.")
    parser.add_argument("--average", type=int, default=5, help="HX711 samples per reading.")
    parser.add_argument("--reference-unit", type=float, default=1.0, help="Reference unit/calibration value.")
    parser.add_argument("--dout", type=int, default=None, help="Override DOUT GPIO pin.")
    parser.add_argument("--sck", type=int, default=None, help="Override SCK GPIO pin.")
    parser.add_argument("--no-tare", action="store_true", help="Initialize hardware but do not tare/zero first.")
    args = parser.parse_args()

    kwargs = {
        "use_mock": False,
        "reference_unit": args.reference_unit,
        "average_samples": args.average,
        "filter_window": 1,
    }
    if args.dout is not None:
        kwargs["dout_pin"] = args.dout
    if args.sck is not None:
        kwargs["pd_sck_pin"] = args.sck

    load_cell = LoadCell(**kwargs)
    print("Load cell diagnostic")
    print(f"DOUT={load_cell.dout_pin} SCK={load_cell.pd_sck_pin} reference_unit={load_cell.reference_unit}")

    if args.no_tare:
        print("Initializing HX711 without tare...")
        load_cell._init_hardware()
    else:
        print("Taring/zeroing HX711. Remove load from the sensor now.")
        time.sleep(2.0)
        if not load_cell.tare():
            print(load_cell.last_error)
            return 1

    print("Pull or press on the load cell now. Ctrl+C stops.")
    print("index, reading, raw, error")
    count = 0
    try:
        while args.samples == 0 or count < args.samples:
            reading = load_cell.get_force()
            print(f"{count + 1}, {reading:.6f}, {load_cell.last_raw_lbs:.6f}, {load_cell.last_error}")
            count += 1
            time.sleep(args.delay)
    except KeyboardInterrupt:
        print("Stopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
