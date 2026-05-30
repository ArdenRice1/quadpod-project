from config import (
    ACTUATOR_INVERT,
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
    ):
        self.use_mock = use_mock
        self.channel = int(channel)
        self.frequency_hz = int(frequency_hz)
        self.address = int(address)
        self.busnum = int(busnum)
        self.invert = bool(invert)
        self.pwm = None
        self.last_command = "neutral"
        self.last_pulse_us = VICTOR_NEUTRAL_US
        self.last_error = ""

        if not self.use_mock:
            self._init_hardware()
        self.stop()

    def _init_hardware(self):
        try:
            import Adafruit_PCA9685

            self.pwm = Adafruit_PCA9685.PCA9685(address=self.address, busnum=self.busnum)
            self.pwm.set_pwm_freq(self.frequency_hz)
            self.last_error = ""
        except Exception as exc:
            self.last_error = f"PCA9685 init failed: {exc}"
            raise

    def move_up(self, fast=False):
        return self._move("up", fast=fast)

    def move_down(self, fast=False):
        return self._move("down", fast=fast)

    def pull(self):
        return self.move_down(fast=False)

    def stop(self):
        return self.set_pulse_us(VICTOR_NEUTRAL_US, command="neutral")

    def _move(self, direction, fast=False):
        physical_direction = self._maybe_invert(direction)
        if fast:
            pulse = VICTOR_JOG_US if physical_direction == "down" else self._mirror(VICTOR_JOG_US)
        else:
            pulse = VICTOR_PULL_US if physical_direction == "down" else self._mirror(VICTOR_PULL_US)
        return self.set_pulse_us(pulse, command=f"{direction}_{'fast' if fast else 'pull'}")

    def _maybe_invert(self, direction):
        if not self.invert:
            return direction
        return "up" if direction == "down" else "down"

    def _mirror(self, pulse_us):
        return int(VICTOR_NEUTRAL_US - (int(pulse_us) - VICTOR_NEUTRAL_US))

    def set_pulse_us(self, pulse_us, command="custom"):
        pulse_us = int(max(min(pulse_us, VICTOR_FORWARD_US), VICTOR_REVERSE_US))
        self.last_command = command
        self.last_pulse_us = pulse_us

        if self.use_mock:
            self.last_error = ""
            return True

        try:
            ticks = self.microseconds_to_ticks(pulse_us)
            self.pwm.set_pwm(self.channel, 0, ticks)
            self.last_error = ""
            return True
        except Exception as exc:
            self.last_error = f"PWM command failed: {exc}"
            return False

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
            "last_command": self.last_command,
            "last_pulse_us": self.last_pulse_us,
        }
