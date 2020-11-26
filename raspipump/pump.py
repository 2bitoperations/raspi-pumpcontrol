import configparser
import datetime
import logging
import math
import time

import requests
from gpiozero import LED

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

# some constants to help define the states we could be in
OFF = 0
ON = 1
# can't talk to the cistern
COMM_ERROR = -1
# a pipe may be broken, the pump may be broken
FAULT = -2

class Cistern:
    def __init__(self,
                 url,
                 timeout):
        self.url = url
        self.timeout = timeout

    def get_reading(self):
        try:
            response = requests.get(self.url, timeout=self.timeout)
            if response.status_code is not 200:
                logging.warning("nonzero status while fetching level %s, body %s" % (response.status_code, response.text))
                return None
            reading = response.json()
            if "level" not in reading or "timestamp" not in reading:
                logging.warning("response did not contain required fields status %s body %s" % (response.status_code, response.text))
                return None
            logging.debug("fetched level as {level} timestamp {timestamp} full body {body}"
                          .format(level=reading["level"], timestamp=reading["timestamp"], body=["body"]))
            return reading
        except Exception as ex:
            logging.exception("error fetching reading")
            return None

    def is_reading_valid(self, reading, max_timedelta_seconds):
        if "timestamp" not in reading:
            logging.debug("reading {reading} missing timestamp. invalid.".format(reading=reading))
            return False
        if "level" not in reading:
            logging.debug("reading {reading} missing level. invalid.".format(reading=reading))
            return False
        now = datetime.datetime.now()
        reading_time = datetime.datetime.utcfromtimestamp(reading["timestamp"])
        delta_seconds = abs(now.timestamp() - reading_time.timestamp()) / 1000
        if delta_seconds < max_timedelta_seconds:
            logging.debug("reading {reading} timedelta {timedelta} within range {max_timedelta_seconds}"
                          .format(reading=reading, timedelta=delta_seconds, max_timedelta_seconds=max_timedelta_seconds))
            return True
        else:
            logging.debug("reading {reading} timedelta {timedelta} outside range {max_timedelta_seconds}"
                          .format(reading=reading, timedelta=delta_seconds, max_timedelta_seconds=max_timedelta_seconds))
            return False

class InitialStateReporter:
    def __init__(self):

    def report_state(self, state):

class Pump:
    def __init__(self,
                 cistern,
                 initialstate_reporter,
                 pump_pin,
                 active_high,
                 max_run_time_minutes,
                 cooldown_minutes,
                 sleep_between_readings_seconds,
                 desired_level,
                 level_must_move_in_seconds):
        self.state=OFF
        self.pump=LED(pump_pin, active_high=active_high)
        self.cistern = cistern
        self.initialstate = initialstate_reporter
        self.pump_off_time = datetime.datetime.utcfromtimestamp(0)
        self.pump_on_time = datetime.datetime.utcfromtimestamp(0)
        self.active_high = active_high
        self.max_run_time_seconds = max_run_time_minutes * 60
        self.cooldown_seconds = cooldown_minutes * 60
        self.sleep_between_readings_seconds = sleep_between_readings_seconds
        self.desired_level = desired_level
        self.level_must_move_in_seconds = level_must_move_in_seconds

    def _is_pump_off(self):
        if self.active_high == 1:
            return self.pump.state
    def _pump_off(self):
        # if the pump isn't already off, record off time.
        if self.pump.is_lit:
            self.pump_off_time = datetime.datetime.now()
        self.pump.off()

    def _pump_on(self, level_at_pump_on):
        if not self.pump.is_lit:
            self.pump_on_time = datetime.datetime.now()
            self.level_at_pump_on = level_at_pump_on
        self.pump.on()

    def run(self):
        try:
            while True:
                logging.debug("starting loop, state is {state}, pump_off_time {pump_off_time}, pump_on_time {pump_on_time}"
                              .format(state=self.state,
                                      pump_off_time=self.pump_off_time,
                                      pump_on_time=self.pump_on_time))
                self.initialstate.report_state(self.state)

                # if we're in a FAULT state, we're stuck here.
                if self.state is FAULT:
                    self._pump_off()
                    time.sleep(self.sleep_between_readings_seconds)
                    continue
                else:
                    # have we exceeded our max allowed runtime?
                    if self.state is ON and not self.max_runtime_allows_running():
                        logging.info("max allowed runtime exceeded, pump off.")
                        self.state = OFF
                        self._pump_off()
                        time.sleep(self.sleep_between_readings_seconds)
                        continue
                    # get a fresh reading from the cistern
                    reading = self.cistern.get_reading()
                    reading_valid = self.cistern.is_reading_valid(reading, max_timedelta_seconds=self.sleep_between_readings_seconds * 2)
                    if not reading_valid:
                        logging.warning("unable to get reading. pump off.")
                        self.state = COMM_ERROR
                        self._pump_off()
                        time.sleep(self.sleep_between_readings_seconds)
                        continue
                    elif reading_valid and (float(reading["level"]) >= float(self.desired_level)):
                        logging.debug("not running pump, level is {level} desired is {desired}"
                                      .format(level=reading["level"], desired=self.desired_level))
                        self.state = OFF
                        self._pump_off()
                        time.sleep(self.sleep_between_readings_seconds)
                        continue
                    elif reading_valid and (float(reading["level"]) < float(self.desired_level)):
                        # valid reading, ideally we want to run the pump. check our cooldown time.
                        if self.state is not ON and self.cooldown_allows_running():
                            # sweet, we can run.
                            logging.info("running pump, level is {level} desired is {desired}"
                                         .format(level=reading["level"], desired=self.desired_level))
                            self.state = ON
                            self._pump_on()
                            time.sleep(self.sleep_between_readings_seconds)
                            continue
                        else:
                            logging.info("not pump, level is {level} desired is {desired}, within cooldown period"
                                         .format(level=reading["level"], desired=self.desired_level))
                            self.state = OFF
                            self._pump_off()
                            time.sleep(self.sleep_between_readings_seconds)
                            continue
        finally:
            logging.info("exiting, about to turn pump off")
            self._pump_off()
            logging.info("exiting, pump is off, exiting.")

    def pipe_break_detect_allows_running(self):


    def max_runtime_allows_running(self):



    def cooldown_allows_running(self):
        total_time_in_cooldown_secs = abs(datetime.datetime.now().timestamp() - self.pump_off_time.timestamp()) / 1000
        logging.debug("total time in cooldown {total_time_in_cooldown_secs} cooldown time {cooldown_time}"
                      .format(total_time_in_cooldown_secs=total_time_in_cooldown_secs,
                              cooldown_time=self.cooldown_seconds))
        return total_time_in_cooldown_secs > self.cooldown_seconds

try:
    pump.off()

finally:
    pump.off()

def u