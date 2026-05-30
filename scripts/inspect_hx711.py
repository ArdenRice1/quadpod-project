#!/usr/bin/env python3
import inspect


def main():
    import RPi.GPIO as GPIO
    from hx711 import HX711

    if hasattr(GPIO, "setwarnings"):
        GPIO.setwarnings(False)

    hx = HX711(dout_pin=5, pd_sck_pin=6)
    public = [name for name in dir(hx) if not name.startswith("_")]
    print("HX711 object:", type(hx))
    print("Public methods/attributes:")
    for name in public:
        attr = getattr(hx, name)
        if callable(attr):
            try:
                signature = str(inspect.signature(attr))
            except (TypeError, ValueError):
                signature = "(...)"
            print(f"  {name}{signature}")
        else:
            print(f"  {name} = {attr!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
