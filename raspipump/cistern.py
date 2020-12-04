import datetime
import logging

import requests


class Cistern:
    def __init__(self,
                 url,
                 timeout_secs):
        self.url = str(url)
        self.timeout_secs = timeout_secs
        logging.info("cistern initialized with url {url} and timeout {timeout}"
                      .format(url=self.url, timeout=self.timeout_secs))

    def get_reading(self):
        try:
            response = requests.get(self.url, timeout=self.timeout_secs)
            if response.status_code is not 200:
                logging.warning(
                    "nonzero status while fetching level %s, body %s" % (response.status_code, response.text))
                return None
            reading = response.json()
            if "level" not in reading or "timestamp" not in reading:
                logging.warning("response did not contain required fields status %s body %s" % (
                response.status_code, response.text))
                return None
            logging.debug("fetched level as {level} timestamp {timestamp} full body {body}"
                          .format(level=reading["level"], timestamp=reading["timestamp"], body=["body"]))
            return reading
        except Exception as ex:
            logging.exception("error fetching reading")
            return None

    @staticmethod
    def is_reading_valid(reading, max_timedelta_seconds):
        if reading is None:
            logging.debug("reading was None")
            return False
        if "timestamp" not in reading:
            logging.debug("reading {reading} missing timestamp. invalid.".format(reading=reading))
            return False
        if "level" not in reading:
            logging.debug("reading {reading} missing level. invalid.".format(reading=reading))
            return False
        now = datetime.datetime.now()
        reading_time = datetime.datetime.utcfromtimestamp(reading["timestamp"] / 1000)
        delta_seconds = abs(now.timestamp() - reading_time.timestamp()) / 1000
        if delta_seconds < max_timedelta_seconds:
            logging.debug("reading {reading} timedelta {timedelta} within range {max_timedelta_seconds}"
                          .format(reading=reading, timedelta=delta_seconds,
                                  max_timedelta_seconds=max_timedelta_seconds))
            return True
        else:
            logging.debug("reading {reading} timedelta {timedelta} outside range {max_timedelta_seconds}"
                          .format(reading=reading, timedelta=delta_seconds,
                                  max_timedelta_seconds=max_timedelta_seconds))
            return False
