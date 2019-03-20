from __future__ import absolute_import, division, print_function

import json
import mimetypes
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.utils import formatdate, make_msgid

import e3.net.smtp
from e3.event.backends.base import Event, EventManager


class SMTPEvent(Event):

    def __init__(self, name, **kwargs):
        super(SMTPEvent, self).__init__(name, **kwargs)
        self.subject = None

    def to_dict(self):
        result = {
            'uid': str(self.uid),
            'name': self.name}
        result.update(self.env.to_dict())
        return result


class SMTPConfig(object):

    def __init__(self, configuration):
        self.subject = configuration['subject']
        self.from_addr = configuration['from_addr']
        self.to_addr = configuration['to_addr']

        # If no smtp server try using sendmail
        self.smtp_servers = configuration.get('smtp_servers', [])


class SMTPEventManager(EventManager):

    Event = SMTPEvent
    Config = SMTPConfig

    def __init__(self, configuration):
        super(SMTPEventManager, self).__init__(configuration)
        self.config = self.Config(configuration)

    def send_event(self, event):
        content = json.dumps(event.to_dict())
        return self.send_email(content, event.attachments,
                               subject=event.subject)

    def send_email(self, json_content, attachments, subject=None):
        mail = MIMEMultipart()
        mail['Subject'] = subject or self.config.subject
        mail['From'] = self.config.from_addr
        mail['To'] = self.config.to_addr
        mail['Date'] = formatdate(localtime=True)
        mail['Message-ID'] = make_msgid()
        mail.preamble = 'You will not see this in a MIME-aware mail reader.\n'
        event_json = MIMEBase('application', 'json')
        event_json.set_payload(json_content)
        encoders.encode_base64(event_json)
        event_json.add_header('Content-Disposition',
                              'attachment', filename='event')
        mail.attach(event_json)

        for name, (filename, _) in attachments.items():
            ctype, encoding = mimetypes.guess_type(filename)

            if encoding == 'gzip' and ctype == 'application/x-tar':
                attachment = MIMEBase('application', 'x-tar-gz')
            elif encoding is None and ctype is not None:
                attachment = MIMEBase(*ctype.split('/', 1))
            else:
                attachment = MIMEBase('application', 'octet-stream')
            with open(filename, 'rb') as data_f:
                attachment.set_payload(data_f.read())

            encoders.encode_base64(attachment)
            attachment.add_header('Content-Disposition', 'attachment',
                                  filename=name)
            mail.attach(attachment)

        return e3.net.smtp.sendmail(
            mail['From'],
            mail['To'].split(','), mail.as_string(),
            self.config.smtp_servers,
            message_id=mail['Message-ID'])
