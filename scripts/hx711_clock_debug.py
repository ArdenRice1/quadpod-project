#!/usr/bin/env python3
import argparse
import time


def pulse(GPIO, sck, delay):
    GPIO.output(sck, True)
    time.sleep(delay)
    GPIO.output(sck, False)
    time.sleep(delay)


def main():
    parser = argparse.ArgumentParser(description="Debug HX711 DOUT/SCK behavior with slow visible clock pulses.")
    parser.add_argument("--dout", type=int, default=5, help="BCM GPIO connected to HX711 DOUT/DT.")
    parser.add_argument("--sck", type=int, default=6, help="BCM GPIO connected to HX711 SCK/PD_SCK.")
    parser.add_argument("--pulse-delay", type=float, default=0.001, help="Delay for each SCK high/low half-cycle.")
    parser.add_argument("--cycles", type=int, default=5, help="Number of 24-bit reads to attempt.")
    parser.add_argument("--wait", type=float, default=1.0, help="Seconds to wait for DOUT ready per cycle.")
    args = parser.parse_args()

    import RPi.GPIO as GPIO

    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(args.sck, GPIO.OUT)
    GPIO.setup(args.dout, GPIO.IN)
    GPIO.output(args.sck, False)
    time.sleep(0.1)

    print(f"HX711 clock debug on BCM DOUT={args.dout}, SCK={args.sck}")
    print("Expected: DOUT high while not ready, low when ready, then 24 data bits change as SCK pulses.")

    try:
        for cycle in range(1, args.cycles + 1):
            print(f"cycle {cycle}: initial DOUT={'HIGH' if GPIO.input(args.dout) else 'LOW'}")
            started = time.monotonic()
            while GPIO.input(args.dout) and time.monotonic() - started < args.wait:
                time.sleep(0.005)
            print(f"cycle {cycle}: ready DOUT={'HIGH' if GPIO.input(args.dout) else 'LOW'}")

            bits = []
            value = 0
            for _ in range(24):
                GPIO.output(args.sck, True)
                time.sleep(args.pulse_delay)
                bit = int(GPIO.input(args.dout))
                bits.append(str(bit))
                value = (value << 1) | bit
                GPIO.output(args.sck, False)
                time.sleep(args.pulse_delay)

            pulse(GPIO, args.sck, args.pulse_delay)
            if value & 0x800000:
                signed = value - 0x1000000
            else:
                signed = value
            print(f"cycle {cycle}: bits={''.join(bits)} raw={signed} after DOUT={'HIGH' if GPIO.input(args.dout) else 'LOW'}")
            time.sleep(0.25)
    finally:
        GPIO.output(args.sck, False)
        GPIO.cleanup((args.dout, args.sck))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
