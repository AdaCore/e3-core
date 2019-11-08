from __future__ import absolute_import
import mimetypes
import tempfile
import json
from contextlib import closing

from e3.event import EventHandler
from e3.fs import rm
from e3.os.process import Run
from e3.sys import python_script


class S3Handler(EventHandler):
    """Event handler that relies on AWS S3."""

    def __init__(self, event_s3_url, log_s3_url, sse='AES256'):
        self.event_s3_url = event_s3_url
        self.log_s3_url = log_s3_url
        self.sse = sse

    @classmethod
    def decode_config(self, config_str):
        event_s3_url, log_s3_url, sse = config_str.split(',', 2)
        return {'event_s3_url': event_s3_url,
                'log_s3_url': log_s3_url,
                'sse': sse}

    def encode_config(self):
        return "%s,%s,%s" % (self.event_s3_url,
                             self.log_s3_url,
                             self.sse)

    def send_event(self, event):
        def s3_cp(from_path, s3_url):
            s3 = Run(python_script('aws') +
                     ['s3', 'cp', '--sse=%s' % self.sse, from_path, s3_url],
                     output=None)
            return s3.status == 0

        # Push attachments to s3 and keep track of their url.
        s3_attachs = {}
        for name, attach in event.get_attachments().items():
            attach_path = attach[0]
            # Push the attachment
            s3_url = "%s/%s/%s" % (self.log_s3_url, event.uid, name)
            success = s3_cp(attach_path, s3_url)
            if not success:
                return False
            else:
                ctype, encoding = mimetypes.guess_type(attach_path)
                s3_attachs[name] = {'s3_url': s3_url,
                                    'encoding': encoding,
                                    'ctype': ctype}

        # Create the JSON to send on the event bucket
        s3_event = {'attachments': s3_attachs,
                    'event': event.as_dict()}

        try:
            tempfile_name = None
            with closing(tempfile.NamedTemporaryFile(mode='wb',
                                                     delete=False)) as fd:
                tempfile_name = fd.name
                json.dump(s3_event, fd)

            success = self.s3_cp(
                tempfile_name,
                "%s/%s" % (self.event_s3_url, event.uid + '.s3'))
            if not success:
                return False
            else:
                return True
        finally:
            if tempfile_name is not None:
                rm(tempfile_name)
