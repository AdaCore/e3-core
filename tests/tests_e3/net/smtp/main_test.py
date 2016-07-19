import mock
import e3.net.smtp


def test_sendmail():
    from_addr = 'e3@example.net'
    to_addresses = ['info@example.net', 'info@example.com']
    msg_as_string = 'test mail content'
    with mock.patch('smtplib.SMTP') as mock_smtp:
        e3.net.smtp.sendmail(
            from_addr,
            to_addresses,
            msg_as_string,
            ['smtp.localhost'])

        smtp_mock = mock_smtp.return_value
        assert smtp_mock.sendmail.called
        assert smtp_mock.sendmail.call_count == 1
        smtp_mock.sendmail.assert_called_once_with(
            from_addr,
            to_addresses,
            msg_as_string)
