import configparser
import logging

from logging import handlers

from raspipump.cistern import Cistern
from raspipump.initialstatereporter import InitialStateReporter
from raspipump.pump import Pump

INITIALSTATE = "initialstate"

rootLogger = logging.getLogger()
rootLogger.setLevel(logging.DEBUG)

ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
rootLogger.addHandler(ch)

fileLogger = logging.FileHandler("/tmp/raspi-pump.log")
fileLogger.setLevel(logging.WARN)
fileLogger.setFormatter(formatter)
rootLogger.addHandler(fileLogger)

# read config
config = configparser.RawConfigParser()
config.read("/etc/raspi-pump.conf")

if config.getboolean("remote-syslog", "enabled"):
    syslogLogger = handlers.SysLogHandler(
        address=(config.get("remote-syslog", "host"), config.getint("remote-syslog", "port")))
    syslogLogger.setLevel(logging.DEBUG)
    rootLogger.addHandler(syslogLogger)

cistern = Cistern(url=config.get("pump", "cistern_url"),
                  timeout_secs=config.getfloat("pump", "cistern_timeout_secs"))
initialstate = InitialStateReporter(enabled=config.getboolean(INITIALSTATE, "enabled"),
                                    access_key=config.get(INITIALSTATE, "access_key"),
                                    bucket_name=config.get(INITIALSTATE, "bucket_name"),
                                    bucket_key=config.get(INITIALSTATE, "bucket_key"),
                                    item_key=config.get(INITIALSTATE, "item_key"))
pump = Pump(cistern=cistern,
            initialstate_reporter=initialstate,
            pump_pin=config.getint("pump", "pump_gpio_pin"),
            active_high=config.getboolean("pump", "pump_gpio_active_high"),
            max_run_time_minutes=config.getfloat("pump", "max_run_time_minutes"),
            cooldown_minutes=config.getfloat("pump", "cooldown_minutes"),
            sleep_between_readings_seconds=config.getfloat("pump", "sleep_between_readings_seconds"),
            desired_level=config.getfloat("pump", "desired_level"),
            level_must_move_in_seconds=config.getfloat("pump", "level_must_move_in_seconds"),
            level_change_threshold=config.getfloat("pump", "level_change_threshold"))
