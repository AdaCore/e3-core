from e3.event import EventHandler
from e3.fs import mkdir, cp
import json
import os


class FileHandler(EventHandler):
    def __init__(self, log_dir):
        self.log_dir = log_dir

    def send_event(self, event):
        d = event.as_dict()
        prefix = "%s-%s" % (d["name"], d["uid"])
        log_file = os.path.join(self.log_dir, prefix + ".log")
        attach_dir = os.path.join(self.log_dir, prefix)
        mkdir(attach_dir)
        with open(log_file, "w") as fd:
            json.dump(d, fd, indent=2, sort_keys=True)
        for name, attachment in list(event.get_attachments().items()):
            cp(attachment[0], os.path.join(attach_dir, name))
        return True

    @classmethod
    def decode_config(self, config_str):
        return {"log_dir": config_str}

    def encode_config(self):
        return self.log_dir
