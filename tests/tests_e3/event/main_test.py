from __future__ import absolute_import, division, print_function

import contextlib
import email
import json
import os

import e3.archive
import e3.event
import e3.fs
import e3.os.fs

import mock


def test_smtp_event():

    manager = e3.event.load_event_manager(
        'smtp',
        {'subject': 'test subject',
         'from_addr': 'e3@example.net',
         'to_addr': 'info@example.net,info@example.com',
         'smtp_servers': ['smtp.localhost']
         })

    e3.fs.mkdir('pkg')
    e3.archive.create_archive(
        filename='pkg.tar.gz',
        from_dir=os.path.join(os.getcwd(), 'pkg'),
        dest=os.getcwd())

    e3.os.fs.touch('unknown')

    with contextlib.closing(manager.Event(
            name='event test')) as e:
        e.attach_file('pkg.tar.gz', name='pkg.tar.gz')
        e.attach_file(__file__, name='test.py')
        e.attach_file('unknown', name='unknown')
        e.subject = 'a test subject'

    with mock.patch('smtplib.SMTP_SSL') as mock_smtp:
        manager.send_event(e)

    smtp_mock = mock_smtp.return_value
    assert smtp_mock.sendmail.called
    assert smtp_mock.sendmail.call_count == 1
    msg_as_string = smtp_mock.sendmail.call_args[0][2]

    event_mail = email.message_from_string(msg_as_string)
    assert event_mail['Subject'] == 'a test subject'

    evdata = None
    attachment_content = None
    for part in event_mail.walk():
        part_type = part.get_content_maintype()
        subpart_type = part.get_content_type().split('/')[1]
        if part_type == 'multipart':
            pass
        elif part_type == 'application' and subpart_type == 'json':
            part_content = part.get_payload(decode=True)
            evdata = json.loads(part_content.decode('utf-8'))
        elif part.get_filename() == 'test.py':
            attachment_content = part.get_payload(decode=True)

    assert evdata is not None, 'no json part found'
    assert evdata['name'] == 'event test'
    assert attachment_content is not None

    # attachment content contains this file content, including
    # the previous line
    assert b'assert attachment_content is not None' in attachment_content
