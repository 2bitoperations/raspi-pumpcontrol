import logging


class InitialStateReporter:
    def __init__(self,
                 enabled,
                 bucket_name,
                 bucket_key,
                 access_key,
                 item_key):
        self.enabled = enabled
        if enabled:
            from ISStreamer.Streamer import Streamer
            self.streamer = Streamer(bucket_name=bucket_name,
                                bucket_key=bucket_key,
                                access_key=access_key)
            self.item_key = item_key

    def report_state(self, state):
        if self.enabled:
            try:
                self.streamer.log(key=self.item_key, value=state)
                self.streamer.flush()
            except Exception as ex:
                logging.exception("unable to report state to initialstate")

    def close(self):
        if self.enabled:
            self.streamer.close()