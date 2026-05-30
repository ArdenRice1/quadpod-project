#!/usr/bin/env python3
import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import PWM_FREQUENCY_HZ, PWM_I2C_ADDRESS, PWM_I2C_BUSNUM, VICTOR_CHANNEL


def microseconds_to_ticks(pulse_us, frequency_hz):
    period_us = 1_000_000.0 / frequency_hz
    return int(round((pulse_us / period_us) * 4096))


def main():
    parser = argparse.ArgumentParser(description="Send one PCA9685/Victor SPX pulse for actuator diagnostics.")
    parser.add_argument("--pulse", type=int, required=True, help="Pulse width in microseconds, for example 1500.")
    parser.add_argument("--hold", type=float, default=1.0, help="Seconds to hold the pulse.")
    parser.add_argument("--channel", type=int, default=VICTOR_CHANNEL, help="PCA9685 channel.")
    parser.add_argument("--address", type=lambda value: int(value, 0), default=PWM_I2C_ADDRESS, help="PCA9685 I2C address.")
    parser.add_argument("--busnum", type=int, default=PWM_I2C_BUSNUM, help="I2C bus number, usually 1 on Raspberry Pi.")
    parser.add_argument("--frequency", type=int, default=PWM_FREQUENCY_HZ, help="PWM frequency in Hz.")
    parser.add_argument("--neutral-after", action="store_true", help="Return to 1500us after the hold instead of disabling PWM.")
    args = parser.parse_args()

    import Adafruit_PCA9685

    pwm = Adafruit_PCA9685.PCA9685(address=args.address, busnum=args.busnum)
    pwm.set_pwm_freq(args.frequency)
    ticks = microseconds_to_ticks(args.pulse, args.frequency)

    print("PCA9685 PWM probe")
    print(f"bus={args.busnum} address=0x{args.address:02x} channel={args.channel} freq={args.frequency}Hz")
    print(f"sending {args.pulse}us -> {ticks} ticks for {args.hold}s")
    pwm.set_pwm(args.channel, 0, ticks)
    time.sleep(args.hold)

    if args.neutral_after:
        neutral_ticks = microseconds_to_ticks(1500, args.frequency)
        print(f"returning to 1500us -> {neutral_ticks} ticks")
        pwm.set_pwm(args.channel, 0, neutral_ticks)
    else:
        print("disabling PWM output on channel")
        pwm.set_pwm(args.channel, 0, 0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
