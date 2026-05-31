#!/usr/bin/env python3
import argparse
import time


def read_samples(GPIO, pin, count, delay):
    values = []
    for _ in range(count):
        values.append(GPIO.input(pin))
        time.sleep(delay)
    return values


def label(value):
    return "HIGH" if value else "LOW"


def main():
    parser = argparse.ArgumentParser(description="Probe Raspberry Pi GPIO pin levels with optional pull resistors.")
    parser.add_argument("--pin", type=int, default=5, help="BCM GPIO pin to read.")
    parser.add_argument("--samples", type=int, default=20, help="Samples per pull mode.")
    parser.add_argument("--delay", type=float, default=0.1, help="Seconds between samples.")
    parser.add_argument("--mode", choices=("input", "toggle"), default="input")
    parser.add_argument("--toggle-delay", type=float, default=0.5, help="Seconds between HIGH/LOW when mode=toggle.")
    parser.add_argument("--toggle-count", type=int, default=20, help="Number of HIGH/LOW output cycles when mode=toggle.")
    args = parser.parse_args()

    import RPi.GPIO as GPIO

    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)

    try:
        if args.mode == "toggle":
            GPIO.setup(args.pin, GPIO.OUT)
            print(f"Toggling BCM GPIO {args.pin}. Measure this pin to GND with a meter if needed.")
            for index in range(args.toggle_count):
                GPIO.output(args.pin, True)
                print(f"{index + 1}: HIGH")
                time.sleep(args.toggle_delay)
                GPIO.output(args.pin, False)
                print(f"{index + 1}: LOW")
                time.sleep(args.toggle_delay)
            return 0

        pull_modes = [
            ("off", GPIO.PUD_OFF),
            ("pull_up", GPIO.PUD_UP),
            ("pull_down", GPIO.PUD_DOWN),
        ]
        for name, pud in pull_modes:
            GPIO.setup(args.pin, GPIO.IN, pull_up_down=pud)
            time.sleep(0.1)
            values = read_samples(GPIO, args.pin, args.samples, args.delay)
            lows = values.count(0)
            highs = values.count(1)
            rendered = " ".join(label(value) for value in values)
            print(f"BCM GPIO {args.pin} with {name}: LOW={lows} HIGH={highs}")
            print(rendered)
        return 0
    finally:
        GPIO.cleanup(args.pin)


if __name__ == "__main__":
    raise SystemExit(main())
