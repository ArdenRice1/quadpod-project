#!/usr/bin/env python3
import argparse
import time


def main():
    parser = argparse.ArgumentParser(description="Check HX711 DOUT pin level without using the HX711 library.")
    parser.add_argument("--dout", type=int, default=5, help="BCM GPIO number connected to HX711 DOUT/DT.")
    parser.add_argument("--seconds", type=float, default=5.0, help="How long to watch the pin.")
    parser.add_argument("--interval", type=float, default=0.05, help="Seconds between samples.")
    args = parser.parse_args()

    import RPi.GPIO as GPIO

    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(args.dout, GPIO.IN)

    low_count = 0
    high_count = 0
    started = time.monotonic()
    print(f"Watching BCM GPIO {args.dout} for {args.seconds}s. HX711 DOUT should pulse low when data is ready.")
    try:
        while time.monotonic() - started < args.seconds:
            value = GPIO.input(args.dout)
            if value:
                high_count += 1
            else:
                low_count += 1
            print("LOW" if value == 0 else "HIGH", flush=True)
            time.sleep(args.interval)
    finally:
        GPIO.cleanup(args.dout)

    print(f"Summary: LOW={low_count} HIGH={high_count}")
    if low_count == 0:
        print("DOUT never went LOW. Check HX711 power, ground, DOUT pin, SCK pin, and BCM-vs-physical pin numbering.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
