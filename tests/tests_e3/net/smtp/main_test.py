import smtplib
from email.utils import make_msgid

import e3.net.smtp
from e3.error import E3Error

import mock
import pytest


def test_sendmail():
    from_addr = "e3@example.net"
    to_addresses = ["info@example.net", "info@example.com"]
    msg_as_string = "test mail content"

    with mock.patch("smtplib.SMTP_SSL") as mock_smtp:
        e3.net.smtp.sendmail(from_addr, to_addresses, msg_as_string, ["smtp.localhost"])

        smtp_mock = mock_smtp.return_value
        assert smtp_mock.sendmail.called
        assert smtp_mock.sendmail.call_count == 1
        smtp_mock.sendmail.assert_called_once_with(
            from_addr, to_addresses, msg_as_string
        )


def test_sendmail_onerror(caplog):
    from_addr = "e3@example.net"
    to_addresses = ["info@example.net", "info@example.com"]
    msg_as_string = "test mail content"
    msg_size_exceed = "A" * 1200
    result = e3.net.smtp.sendmail(
        from_addr, to_addresses, msg_size_exceed, ["smtp.localhost"], max_size=1 / 1024
    )
    assert result is False
    assert "message file too big" in caplog.text

    with mock.patch("smtplib.SMTP_SSL") as mock_smtp:
        mock_smtp.side_effect = smtplib.SMTPException()
        result = e3.net.smtp.sendmail(
            from_addr, to_addresses, msg_as_string, ["smtp.localhost"]
        )
        assert result is False

    with mock.patch("smtplib.SMTP_SSL") as mock_smtp:
        smtp_mock = mock_smtp.return_value
        smtp_mock.sendmail.side_effect = smtplib.SMTPException()
        result = e3.net.smtp.sendmail(
            from_addr, to_addresses, msg_as_string, ["smtp.localhost"]
        )
        assert result is False

    with mock.patch("smtplib.SMTP_SSL") as mock_smtp:
        smtp_mock = mock_smtp.return_value
        smtp_mock.sendmail.return_value = {}

        mid = make_msgid()
        result = e3.net.smtp.sendmail(
            from_addr, to_addresses, msg_as_string, ["smtp.localhost"], message_id=mid
        )
        assert result is True
        assert "Message-ID: %s sent successfully" % mid in caplog.text
        assert "smtp quit" in caplog.text

    with mock.patch("smtplib.SMTP_SSL") as mock_smtp:
        smtp_mock = mock_smtp.return_value
        smtp_mock.sendmail.return_value = {}

        def error_on_quit():
            raise smtplib.SMTPException("error on quit ignored")

        smtp_mock.quit = error_on_quit
        mid = make_msgid()
        result = e3.net.smtp.sendmail(
            from_addr, to_addresses, msg_as_string, ["smtp.localhost"], message_id=mid
        )
        assert result is True
        assert "Message-ID: %s sent successfully" % mid in caplog.text


def test_send_message():
    from_addr = "e3@example.net"
    to_addresses = ["info@example.net", "info@example.com"]
    msg_content = "test mail content"
    msg_subject = "test mail subject"

    with mock.patch("smtplib.SMTP_SSL") as mock_smtp:
        smtp_mock = mock_smtp.return_value
        smtp_mock.sendmail.return_value = {}
        e3.net.smtp.send_message(
            from_addr, to_addresses, msg_subject, msg_content, ["smtp.localhost"]
        )

        assert smtp_mock.sendmail.called
        assert smtp_mock.sendmail.call_count == 1

        smtp_mock.sendmail.return_value = {"error": 2}

        with pytest.raises(E3Error):
            e3.net.smtp.send_message(
                from_addr, to_addresses, msg_subject, msg_content, ["smtp.localhost"]
            )
