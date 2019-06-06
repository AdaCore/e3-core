from __future__ import absolute_import, division, print_function

import json
import mimetypes
import os
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.utils import formatdate, make_msgid

import e3.net.smtp
from e3.event.backends.base import Event, EventManager
from e3.fs import mkdir


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
        if isinstance(self.smtp_servers, str):
            self.smtp_servers = [self.smtp_servers]


class SMTPEventManager(EventManager):

    Event = SMTPEvent
    Config = SMTPConfig

    def __init__(self, configuration):
        """Initialize a SMTP event manager.

        :param configuration: a dictionary with config parameters
        :type configuration: dict
        """
        super(SMTPEventManager, self).__init__(configuration)
        self.config = self.Config(configuration)

    def send_event(self, event):
        """Send an event.

        :param event: an event
        :type event: SMTPEvent
        :return: True if the event was sent successfully
        :rtype: bool
        """
        result = self.create_email(event)
        return self.send_email(result)

    def dump_event(self, event, dest):
        """Dump an email event into a json file.

        :param event: an event as a dict
        :type event: SMTPEvent
        :param dest: destination directory. If the directory does not exist
            it is created
        :type dest: str
        :type dest: str
        :return: a path to the json file. the file name is unique as it is
            based on the message id
        :rtype: str
        """
        event_dict = self.create_email(event)
        mkdir(dest)
        event_file = os.path.join(
            dest,
            event_dict['message_id'].replace('<', '').replace('>', '') +
            '.json')
        with open(event_file, 'w') as fd:
            json.dump(event_dict, fd, indent=2)
        return event_file

    def create_email(self, event):
        """Create an event as email.

        :param event: an event
        :type event: SMTPEvent
        :return: a dictionary with the following keys: ```from``` for from
            address, ```content``` for the email body as a string, ```to```
            for the destination address. ```smtp_server``` for a list of smtp
            servers to try and ```message_id``` for the email message id.
        :rtype: dict
        """
        json_content = json.dumps(event.to_dict())
        attachments = event.attachments
        subject = event.subject

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

        result = {'attachments': {}}

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

            result['attachments'][name] = {'path': filename,
                                           'encoding': encoding,
                                           'ctype': ctype}

            encoders.encode_base64(attachment)
            attachment.add_header('Content-Disposition', 'attachment',
                                  filename=name)
            mail.attach(attachment)
        result.update(
            {'from': self.config.from_addr,
             'to': mail['To'].split(','),
             'content': mail.as_string(),
             'event_dict': event.to_dict(),
             'smtp_server': self.config.smtp_servers,
             'message_id': mail['Message-ID']})
        return result

    @classmethod
    def send_event_from_file(cls, event_path):
        """Load an event from a json file and send it.

        :param event_path: path to a JSON file
        :type event_path: str
        :return: True if the email is successfully sent.
        :rtype: bool
        """
        with open(event_path, 'r') as fd:
            msg = json.load(fd)

        return cls.send_email(msg)

    @classmethod
    def send_email(cls, email_dict):
        """Send the email corresponding to the event.

        :param: a dict as returned by create_email.
        :type: dict
        :return: True if the email is successfully sent.
        :rtype: bool
        """
        return e3.net.smtp.sendmail(
            email_dict['from'],
            email_dict['to'],
            email_dict['content'],
            email_dict['smtp_server'],
            message_id=email_dict['message_id'])
