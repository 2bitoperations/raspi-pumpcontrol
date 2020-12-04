# raspi-pumpcontrol
A project to control a well pump with GPIO pins on a pi in order to keep a cistern (that is far away from the well pump) monitored by the excellent raspi-sump project (https://github.com/alaudet/raspi-sump) filled to a specific level.

# install
OpenWRT, by default, does not provide /dev/mem with most of the python raspi GPIO drivers require. If you're not running on OpenWRT:

inside your config file:
```
[gpio]
# can choose between gpiozero or sysfs
driver = gpiozero
```

```
pip3 install gpiozero RPi.GPIO
pip3 install ./
```

If you ARE running on OpenWRT, you'll need to use the GPIO API from the /sys filesystem.

inside your config file:
```
[gpio]
# can choose between gpiozero or sysfs
driver = sysfs
```
```
opkg install python3-pip
pip3 install ./
```


