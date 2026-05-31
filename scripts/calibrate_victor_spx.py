#!/usr/bin/env python3
import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import (
    PWM_FREQUENCY_HZ,
    PWM_I2C_ADDRESS,
    PWM_I2C_BUSNUM,
    VICTOR_CHANNEL,
    VICTOR_FORWARD_US,
    VICTOR_NEUTRAL_US,
    VICTOR_REVERSE_US,
)


def microseconds_to_ticks(pulse_us, frequency_hz):
    period_us = 1_000_000.0 / frequency_hz
    return int(round((pulse_us / period_us) * 4096))


def set_pulse(pwm, channel, frequency_hz, pulse_us, label):
    ticks = microseconds_to_ticks(pulse_us, frequency_hz)
    print(f"{label}: {pulse_us}us -> {ticks} ticks")
    pwm.set_pwm(channel, 0, ticks)


def countdown(seconds, message):
    for remaining in range(seconds, 0, -1):
        print(f"{message} {remaining}...")
        time.sleep(1)


def main():
    parser = argparse.ArgumentParser(
        description="Generate Victor SPX full-forward/full-reverse/neutral PWM signals for B/C CAL calibration."
    )
    parser.add_argument("--channel", type=int, default=VICTOR_CHANNEL, help="PCA9685 PWM channel.")
    parser.add_argument("--address", type=lambda value: int(value, 0), default=PWM_I2C_ADDRESS, help="PCA9685 I2C address.")
    parser.add_argument("--busnum", type=int, default=PWM_I2C_BUSNUM, help="I2C bus number, usually 1 on Raspberry Pi.")
    parser.add_argument("--frequency", type=int, default=PWM_FREQUENCY_HZ, help="PWM frequency in Hz.")
    parser.add_argument("--forward", type=int, default=VICTOR_FORWARD_US, help="Full forward pulse in microseconds.")
    parser.add_argument("--reverse", type=int, default=VICTOR_REVERSE_US, help="Full reverse pulse in microseconds.")
    parser.add_argument("--neutral", type=int, default=VICTOR_NEUTRAL_US, help="Neutral pulse in microseconds.")
    parser.add_argument("--hold", type=float, default=2.0, help="Seconds to hold each full-scale signal.")
    parser.add_argument("--cycles", type=int, default=2, help="Number of forward/reverse cycles while B/C CAL is held.")
    parser.add_argument("--no-prompts", action="store_true", help="Run without waiting for Enter prompts.")
    args = parser.parse_args()

    import Adafruit_PCA9685

    pwm = Adafruit_PCA9685.PCA9685(address=args.address, busnum=args.busnum)
    pwm.set_pwm_freq(args.frequency)

    print("Victor SPX calibration helper")
    print(f"bus={args.busnum} address=0x{args.address:02x} channel={args.channel} frequency={args.frequency}Hz")
    print(f"forward={args.forward}us reverse={args.reverse}us neutral={args.neutral}us")
    print("")
    print("Stop the Flask app before running this. Keep a hand near power.")
    print("Press and hold the Victor SPX B/C CAL button until its LEDs rapidly blink red/green.")
    if not args.no_prompts:
        input("When the LEDs are rapidly blinking and you are still holding B/C CAL, press Enter here...")
    else:
        countdown(5, "Starting calibration signal sequence in")

    try:
        for cycle in range(1, args.cycles + 1):
            print(f"Cycle {cycle} of {args.cycles}")
            set_pulse(pwm, args.channel, args.frequency, args.forward, "full forward")
            time.sleep(args.hold)
            set_pulse(pwm, args.channel, args.frequency, args.reverse, "full reverse")
            time.sleep(args.hold)

        set_pulse(pwm, args.channel, args.frequency, args.neutral, "neutral")
        print("")
        print("Leave the input at neutral now. Release the B/C CAL button.")
        print("Green blinks mean calibration accepted; red blinks mean it failed and kept the previous calibration.")
        if not args.no_prompts:
            input("After checking the Victor LEDs, press Enter to finish and keep neutral output...")
        return 0
    except KeyboardInterrupt:
        print("Interrupted. Returning to neutral.")
        set_pulse(pwm, args.channel, args.frequency, args.neutral, "neutral")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
