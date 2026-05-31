#!/usr/bin/env python3
import argparse
import time


def wait_ready(GPIO, dout, timeout):
    started = time.monotonic()
    while GPIO.input(dout):
        if time.monotonic() - started >= timeout:
            return False
    return True


def read_raw(GPIO, dout, sck, gain_pulses=1, timeout=1.0):
    if not wait_ready(GPIO, dout, timeout):
        raise TimeoutError("HX711 DOUT did not go LOW/data-ready before timeout")

    value = 0
    for _ in range(24):
        GPIO.output(sck, True)
        value = (value << 1) | int(GPIO.input(dout))
        GPIO.output(sck, False)

    for _ in range(gain_pulses):
        GPIO.output(sck, True)
        GPIO.output(sck, False)

    if value & 0x800000:
        value -= 0x1000000
    return value


def main():
    parser = argparse.ArgumentParser(description="Fast manual HX711 raw reader with short SCK high time.")
    parser.add_argument("--dout", type=int, default=5)
    parser.add_argument("--sck", type=int, default=6)
    parser.add_argument("--samples", type=int, default=0, help="0 means endless.")
    parser.add_argument("--delay", type=float, default=0.1)
    parser.add_argument("--timeout", type=float, default=1.0)
    args = parser.parse_args()

    import RPi.GPIO as GPIO

    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(args.sck, GPIO.OUT)
    GPIO.setup(args.dout, GPIO.IN)
    GPIO.output(args.sck, False)

    print(f"Fast HX711 raw read on BCM DOUT={args.dout} SCK={args.sck}. Ctrl+C stops.")
    print("index, raw, delta_from_first")
    first = None
    count = 0
    try:
        while args.samples == 0 or count < args.samples:
            try:
                raw = read_raw(GPIO, args.dout, args.sck, timeout=args.timeout)
                if first is None:
                    first = raw
                print(f"{count + 1}, {raw}, {raw - first}", flush=True)
            except Exception as exc:
                print(f"{count + 1}, ERROR: {exc}", flush=True)
            count += 1
            time.sleep(args.delay)
    except KeyboardInterrupt:
        print("Stopped.")
    finally:
        GPIO.output(args.sck, False)
        GPIO.cleanup((args.dout, args.sck))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
