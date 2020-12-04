import collections
import datetime
import logging
import math
import time

# some constants to help define the states we could be in
OFF = 0
ON = 1
# can't talk to the cistern
COMM_ERROR = -1
# a pipe may be broken, the pump may be broken
FAULT = -2

DRIVER_SYSFS = "sysfs"
DRIVER_GPIOZERO = "gpiozero"

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
                 level_must_move_in_seconds,
                 level_change_threshold,
                 driver):
        self.state = OFF

        if driver == "gpiozero":
            from gpiozero import LED
            self.pump = LED(pump_pin, active_high=active_high)
        elif driver == "sysfs":
            from raspipump.sysfsled import SysFSLed
            self.pump = SysFSLed(pin=pump_pin, active_high=active_high)
        self.pump.off()
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
        self.level_change_threshold = level_change_threshold

    def _pump_off(self):
        # if the pump isn't already off, record off time.
        if self.pump.is_lit:
            self.pump_off_time = datetime.datetime.now()
        self.pump.off()

    def _pump_on(self, level_at_pump_on):
        if not self.pump.is_lit:
            self.pump_on_history = collections.deque([], maxlen=math.ceil(
                self.level_must_move_in_seconds / self.sleep_between_readings_seconds))
            self.pump_on_time = datetime.datetime.now()
            self.level_at_pump_on = level_at_pump_on
        else:
            self.pump_on_history.append({"time": datetime.datetime.now(),
                                         "level": float(level_at_pump_on)})
        self.pump.on()

    def run(self):
        try:
            while True:
                logging.debug(
                    "starting loop, state is {state}, pump_off_time {pump_off_time}, pump_on_time {pump_on_time}, pump on? {pump_on}"
                    .format(state=self.state,
                            pump_off_time=self.pump_off_time,
                            pump_on_time=self.pump_on_time,
                            pump_on=self.pump.is_lit))
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
                    reading_valid = self.cistern.is_reading_valid(reading,
                                                                  max_timedelta_seconds=self.sleep_between_readings_seconds * 2)
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
                        if (self.state is not ON and self.cooldown_allows_running()) or \
                                (self.state is ON and self.pipe_break_detect_allows_running(
                                ) and self.max_runtime_allows_running()):
                            # sweet, we can run.
                            logging.info("running pump, level is {level} desired is {desired}"
                                         .format(level=reading["level"], desired=self.desired_level))
                            self.state = ON
                            self._pump_on(level_at_pump_on=float(reading["level"]))
                            time.sleep(self.sleep_between_readings_seconds)
                            continue
                        elif self.state is OFF or self.state is COMM_ERROR and not self.cooldown_allows_running():
                            logging.info("not pump, level is {level} desired is {desired}, within cooldown period"
                                         .format(level=reading["level"], desired=self.desired_level))
                            self.state = OFF
                            self._pump_off()
                            time.sleep(self.sleep_between_readings_seconds)
                            continue
                        elif self.state is ON and not self.max_runtime_allows_running():
                            logging.info("not pump, level is {level} desired is {desired}, exceeded max runtime"
                                         .format(level=reading["level"], desired=self.desired_level))
                            self.state = OFF
                            self._pump_off()
                            time.sleep(self.sleep_between_readings_seconds)
                            continue
                        elif self.state is ON and not self.pipe_break_detect_allows_running(
                        ):
                            logging.warning("fault! level is {level} desired is {desired}, pipe break fault suspected"
                                            .format(level=reading["level"], desired=self.desired_level))
                            self.state = FAULT
                            self._pump_off()
                            time.sleep(self.sleep_between_readings_seconds)
                            continue
                        else:
                            logging.warning(
                                "fault! level is {level} desired is {desired} state is {state}, unsupported state condition!"
                                .format(level=reading["level"],
                                        desired=self.desired_level,
                                        state=self.state))
                            self.state = FAULT
                            self._pump_off()
                            time.sleep(self.sleep_between_readings_seconds)
                            continue

        finally:
            logging.info("exiting, about to turn pump off")
            self.initialstate.report_state(OFF)
            self._pump_off()
            logging.info("exiting, pump is off, exiting.")

    def pipe_break_detect_allows_running(self):
        total_time_running_secs = abs(datetime.datetime.now().timestamp() - self.pump_on_time.timestamp())
        logging.debug(f"total running time {total_time_running_secs} history {self.pump_on_history}")
        if total_time_running_secs < self.level_must_move_in_seconds:
            return True
        else:
            running_value_change = []
            for i in range(1, len(self.pump_on_history)):
                running_value_change.append(
                    abs(self.pump_on_history[i]["level"] - self.pump_on_history[i + 1]["level"]))
            total_value_change = sum(running_value_change)
            logging.debug(
                f"total running time {total_time_running_secs} history {self.pump_on_history} "
                f"total change {total_value_change} threshold {self.level_change_threshold}")
            return total_value_change > float(self.level_change_threshold)

    def max_runtime_allows_running(self):
        total_time_running_secs = abs(datetime.datetime.now().timestamp() - self.pump_on_time.timestamp())
        logging.debug(f"total running time {total_time_running_secs} max allowed time {self.max_run_time_seconds}")
        return float(total_time_running_secs) < float(self.max_run_time_seconds)

    def cooldown_allows_running(self):
        total_time_in_cooldown_secs = abs(datetime.datetime.now().timestamp() - self.pump_off_time.timestamp())
        logging.debug("total time in cooldown {total_time_in_cooldown_secs} cooldown time {cooldown_time}"
                      .format(total_time_in_cooldown_secs=total_time_in_cooldown_secs,
                              cooldown_time=self.cooldown_seconds))
        return float(total_time_in_cooldown_secs) > float(self.cooldown_seconds)
