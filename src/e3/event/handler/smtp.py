import json
import mimetypes
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.utils import formatdate, make_msgid

import e3.net.smtp
from e3.event import EventHandler


class SMTPHandler(EventHandler):
    def __init__(self, subject, from_addr, to_addr, smtp_servers):
        """Initialize a SMTP event manager.

        :param configuration: a dictionary with config parameters
        :type configuration: dict
        """
        self.default_subject = subject
        self.from_addr = from_addr
        self.to_addr = to_addr
        if isinstance(smtp_servers, str):
            self.smtp_servers = [smtp_servers]
        else:
            self.smtp_servers = smtp_servers

    @classmethod
    def decode_config(self, config_str):
        subject, from_addr, to_addr, smtp_servers = config_str.split(",", 3)
        smtp_servers = config_str.split(",")
        return {
            "subject": subject,
            "from_addr": from_addr,
            "to_addr": to_addr,
            "smtp_servers": smtp_servers,
        }

    def encode_config(self):
        return "%s,%s,%s,%s" % (
            self.subject,
            self.from_addr,
            self.to_addr,
            ",".join(self.smtp_servers),
        )

    @property
    def subject(self):
        return self.default_subject

    def send_event(self, event):
        """Send an event.

        :param event: an event
        :type event: SMTPEvent
        :return: True if the event was sent successfully
        :rtype: bool
        """
        json_content = json.dumps(event.as_dict())
        attachments = event.get_attachments()

        mail = MIMEMultipart()
        mail["Subject"] = self.subject
        mail["From"] = self.from_addr
        mail["To"] = self.to_addr
        mail["Date"] = formatdate(localtime=True)
        mail["Message-ID"] = make_msgid()
        mail.preamble = "You will not see this in a MIME-aware mail reader.\n"
        event_json = MIMEBase("application", "json")
        event_json.set_payload(json_content)
        encoders.encode_base64(event_json)
        event_json.add_header("Content-Disposition", "attachment", filename="event")
        mail.attach(event_json)

        result = {"attachments": {}}

        for name, (filename, _) in list(attachments.items()):
            ctype, encoding = mimetypes.guess_type(filename)

            if encoding == "gzip" and ctype == "application/x-tar":
                attachment = MIMEBase("application", "x-tar-gz")
            elif encoding is None and ctype is not None:
                attachment = MIMEBase(*ctype.split("/", 1))
            else:
                attachment = MIMEBase("application", "octet-stream")
            with open(filename, "rb") as data_f:
                attachment.set_payload(data_f.read())

            result["attachments"][name] = {
                "path": filename,
                "encoding": encoding,
                "ctype": ctype,
            }

            encoders.encode_base64(attachment)
            attachment.add_header("Content-Disposition", "attachment", filename=name)
            mail.attach(attachment)

        return e3.net.smtp.sendmail(
            self.from_addr,
            mail["To"].split(","),
            mail.as_string(),
            self.smtp_servers,
            message_id=mail["Message-ID"],
        )
