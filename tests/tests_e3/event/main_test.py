import email
import json
import os

import e3.archive
import e3.event
import e3.fs
import e3.os.fs

import mock


def test_smtp_event():

    e3.event.add_handler(
        "smtp",
        subject="test subject",
        from_addr="e3@example.net",
        to_addr="info@example.net,info@example.com",
        smtp_servers=["smtp.localhost"],
    )

    e3.event.add_handler("file", log_dir="./log")

    e3.fs.mkdir("log")
    e3.fs.mkdir("pkg")
    e3.archive.create_archive(
        filename="pkg.tar.gz",
        from_dir=os.path.join(os.getcwd(), "pkg"),
        dest=os.getcwd(),
    )

    e3.os.fs.touch("unknown")

    with e3.event.Event(name="event test") as e:
        e.attach_file("pkg.tar.gz", name="pkg.tar.gz")
        e.attach_file(__file__, name="test.py")
        e.attach_file("unknown", name="unknown")
        e.attr = "a test attr"

    with mock.patch("smtplib.SMTP_SSL") as mock_smtp:
        e3.event.send_event(e)

    smtp_mock = mock_smtp.return_value
    assert smtp_mock.sendmail.called
    assert smtp_mock.sendmail.call_count == 1
    msg_as_string = smtp_mock.sendmail.call_args[0][2]

    event_mail = email.message_from_string(msg_as_string)
    assert event_mail["Subject"] == "test subject"

    evdata = None
    attachment_content = None
    for part in event_mail.walk():
        part_type = part.get_content_maintype()
        subpart_type = part.get_content_type().split("/")[1]
        if part_type == "multipart":
            pass
        elif part_type == "application" and subpart_type == "json":
            part_content = part.get_payload(decode=True)
            evdata = json.loads(part_content.decode("utf-8"))
        elif part.get_filename() == "test.py":
            attachment_content = part.get_payload(decode=True)

    assert evdata is not None, "no json part found"
    assert evdata["name"] == "event test"
    assert evdata["attr"] == "a test attr"
    assert attachment_content is not None

    # attachment content contains this file content, including
    # the previous line
    assert b"assert attachment_content is not None" in attachment_content

    # Test sending an event in two steps: save in temporary files and then
    # reread the file and send the event.
    filename = e.dump(event_dir=".")
    assert os.path.isfile(filename)

    with mock.patch("smtplib.SMTP_SSL") as mock_smtp:
        e3.event.send_event_from_file(filename)

    smtp_mock = mock_smtp.return_value
    assert smtp_mock.sendmail.called
    assert smtp_mock.sendmail.call_count == 1
    msg_as_string = smtp_mock.sendmail.call_args[0][2]

    event_mail = email.message_from_string(msg_as_string)
    assert event_mail["Subject"] == "test subject"


def test_smtp_servers_as_str():
    """Test when smtp server setting is a string."""
    e3.event.add_handler(
        "smtp",
        subject="test subject",
        from_addr="e3@example.net",
        to_addr="info@example.net,info@example.com",
        smtp_servers="smtp.localhost",
    )
    assert isinstance(e3.event.default_manager.handlers["smtp"].smtp_servers, list)
