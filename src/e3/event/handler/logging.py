from e3.event import EventHandler
import json
import logging
import e3.log


class LoggingHandler(EventHandler):
    def __init__(self, logger_name="", level=logging.DEBUG):
        self.logger_name = logger_name
        self.level = level
        self.log = e3.log.getLogger(logger_name)

    def send_event(self, event):
        d = event.as_dict()
        self.log.log(self.level, json.dumps(d, indent=2))

    def decode_config(self, config_str):
        logger_name, level = config_str.split(",")
        level = int(level)
        return {"logger_name": logger_name, "level": level}

    def encode_config(self):
        return "%s,%s" % (self.logger_name, self.level)
