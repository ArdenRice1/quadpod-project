import atexit
import time

from config import (
    ACTUATOR_INVERT,
    ACTUATOR_PULL_DIRECTION,
    PWM_FREQUENCY_HZ,
    PWM_I2C_ADDRESS,
    PWM_I2C_BUSNUM,
    USE_MOCK_HARDWARE,
    VICTOR_CHANNEL,
    VICTOR_FORWARD_US,
    VICTOR_JOG_US,
    VICTOR_NEUTRAL_US,
    VICTOR_PULL_US,
    VICTOR_REVERSE_US,
)


class Actuator:
    def __init__(
        self,
        use_mock=USE_MOCK_HARDWARE,
        channel=VICTOR_CHANNEL,
        frequency_hz=PWM_FREQUENCY_HZ,
        address=PWM_I2C_ADDRESS,
        busnum=PWM_I2C_BUSNUM,
        invert=ACTUATOR_INVERT,
        pull_direction=ACTUATOR_PULL_DIRECTION,
    ):
        self.use_mock = use_mock
        self.channel = int(channel)
        self.frequency_hz = int(frequency_hz)
        self.address = int(address)
        self.busnum = int(busnum)
        self.invert = bool(invert)
        self.pull_direction = pull_direction if pull_direction in {"up", "down"} else "down"
        self.pwm = None
        self.last_command = "neutral"
        self.last_pulse_us = VICTOR_NEUTRAL_US
        self.last_error = ""
        self._mock_pwm_fail = 0  # test hook: simulate N consecutive PWM failures

        if not self.use_mock:
            self._init_hardware()
        self.stop()
        if not self.use_mock:
            # If the process ever exits or crashes, force the actuator to neutral so
            # the PCA9685 can't be left latching a moving pulse with no software running.
            atexit.register(self.close)

    def _init_hardware(self):
        try:
            import Adafruit_PCA9685

            self.pwm = Adafruit_PCA9685.PCA9685(address=self.address, busnum=self.busnum)
            self.pwm.set_pwm_freq(self.frequency_hz)
            self.last_error = ""
        except Exception as exc:
            self.last_error = f"PCA9685 init failed: {exc}"
            raise

    def move_up(self, fast=False, speed_percent=100):
        return self._move("up", fast=fast, speed_percent=speed_percent)

    def move_down(self, fast=False, speed_percent=100):
        return self._move("down", fast=fast, speed_percent=speed_percent)

    def pull(self):
        if self.pull_direction == "up":
            return self.move_up(fast=False)
        return self.move_down(fast=False)

    def stop(self):
        # Retry the neutral command: a single I2C hiccup must not leave the
        # actuator latched in a moving pulse.
        return self.set_pulse_us(VICTOR_NEUTRAL_US, command="neutral", retries=3)

    def close(self):
        """Best-effort force to neutral (shutdown / atexit backstop)."""
        try:
            self.set_pulse_us(VICTOR_NEUTRAL_US, command="neutral", retries=3)
        except Exception:
            pass

    def _move(self, direction, fast=False, speed_percent=100):
        physical_direction = self._maybe_invert(direction)
        if fast:
            target = VICTOR_JOG_US if physical_direction == "down" else self._mirror(VICTOR_JOG_US)
            pulse = self._scale_speed(target, speed_percent)
        else:
            pulse = VICTOR_PULL_US if physical_direction == "down" else self._mirror(VICTOR_PULL_US)
        return self.set_pulse_us(pulse, command=f"{direction}_{'fast' if fast else 'pull'}")

    def _maybe_invert(self, direction):
        if not self.invert:
            return direction
        return "up" if direction == "down" else "down"

    def _mirror(self, pulse_us):
        return int(VICTOR_NEUTRAL_US - (int(pulse_us) - VICTOR_NEUTRAL_US))

    def _scale_speed(self, target_us, speed_percent):
        percent = max(1.0, min(100.0, float(speed_percent or 100))) / 100.0
        return int(round(VICTOR_NEUTRAL_US + ((int(target_us) - VICTOR_NEUTRAL_US) * percent)))

    def _apply_pulse(self, pulse_us):
        """Push one pulse to the PWM hardware (or the mock). Raises on failure."""
        if self.use_mock:
            if self._mock_pwm_fail > 0:
                self._mock_pwm_fail -= 1
                raise RuntimeError("simulated PWM failure")
            return
        ticks = self.microseconds_to_ticks(pulse_us)
        self.pwm.set_pwm(self.channel, 0, ticks)

    def set_pulse_us(self, pulse_us, command="custom", retries=0):
        pulse_us = int(max(min(pulse_us, VICTOR_FORWARD_US), VICTOR_REVERSE_US))
        self.last_command = command
        self.last_pulse_us = pulse_us

        attempt = 0
        while True:
            try:
                self._apply_pulse(pulse_us)
                self.last_error = ""
                return True
            except Exception as exc:
                self.last_error = f"PWM command failed: {exc}"
                if attempt >= retries:
                    return False
                attempt += 1
                time.sleep(0.01)

    def microseconds_to_ticks(self, pulse_us):
        period_us = 1_000_000.0 / self.frequency_hz
        return int(round((pulse_us / period_us) * 4096))

    def health(self):
        return {
            "mock": self.use_mock,
            "ok": not self.last_error,
            "last_error": self.last_error,
            "channel": self.channel,
            "busnum": self.busnum,
            "pull_direction": self.pull_direction,
            "last_command": self.last_command,
            "last_pulse_us": self.last_pulse_us,
        }
