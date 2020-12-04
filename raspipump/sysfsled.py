from os import path


class SysFSLed:
    def __init__(self, pin, active_high):
        gpio_base_id = None
        self.requested_pin_sysfs_id = None
        self.is_lit = False
        with open("/sys/class/gpio/gpiochip0/base", "r") as gpio_base_file:
            gpio_base_id = int(gpio_base_file.readline())
            self.requested_pin_sysfs_id = gpio_base_id + int(pin)

        if not path.exists("/sys/class/gpio/gpio{pin}".format(pin=self.requested_pin_sysfs_id)):
            with open("/sys/class/gpio/export", "w") as gpio_export_file:
                gpio_export_file.write("{pin}".format(pin=self.requested_pin_sysfs_id))

        with open("/sys/class/gpio/gpio{pin}/direction".format(pin=self.requested_pin_sysfs_id), "w") as gpio_direction_file:
            gpio_direction_file.write("out")

        if not active_high:
            with open("/sys/class/gpio/gpio{pin}/active_low".format(pin=self.requested_pin_sysfs_id), "w") as gpio_active_low_file:
                gpio_direction_file.write("1")

        self.off()

    def off(self):
        with open("/sys/class/gpio/gpio{pin}/value".format(pin=self.requested_pin_sysfs_id), "w") as gpio_pin:
            gpio_pin.write("0")
            self.is_lit = False

    def on(self):
        with open("/sys/class/gpio/gpio{pin}/value".format(pin=self.requested_pin_sysfs_id), "w") as gpio_pin:
            gpio_pin.write("1")
            self.is_lit = True
