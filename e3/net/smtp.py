import os
import smtplib
import socket

import e3.log
import e3.os.process

logger = e3.log.getLogger("net.smtp")


system_sendmail_fallback = False


def sendmail(
    from_email, to_emails, mail_as_string, smtp_servers, max_size=20, message_id=None
):
    """Send an email with stmplib.

    Fallback to /usr/lib/sendmail or /usr/sbin/sendmail if
    ``e3.net.smtp.system_sendmail_fallback`` is set to True (default False).

    :param from_email: the address sending this email (e.g. user@example.com)
    :type from_email: str
    :param to_emails: A list of addresses to send this email to.
    :type to_emails: list[str]
    :param mail_as_string: the message to send (with headers)
    :type mail_as_string: str
    :param smtp_servers: list of smtp server names (hostname), in case of
       exception on a server, the next server in the list will be tried
    :type smtp_servers: list[str]
    :param max_size: do not send the email via smptlib if bigger than
        'max_size' Mo.
    :type max_size: int
    :param message_id: the message id (for debugging purposes)
    :type message_id: str

    :return: boolean (sent / not sent)
    :rtype: bool

    We prefer running smtplib so we can manage the email size.
    We run sendmail in case it fails, assuming the max_size on the system
    is high enough - the advantage of sendmail is that it queues the
    email and retries a few times if the target server is unable
    to receive it.
    """
    mail_size = float(len(mail_as_string)) / (1024 * 1024)
    if mail_size >= max_size:
        # Message too big
        logger.error("!!! message file too big (>= %d Mo): %f Mo", max_size, mail_size)
        return False

    def system_sendmail():
        """Run the system sendmail."""
        if system_sendmail_fallback:
            for sendmail_bin in (
                "/usr/lib/sendmail",
                "/usr/sbin/sendmail",
            ):  # all: no cover
                if os.path.exists(sendmail_bin):
                    p = e3.os.process.Run(
                        [sendmail_bin] + to_emails,
                        input="|" + mail_as_string,
                        output=None,
                    )
                    return p.status == 0

        # No system sendmail, return False
        return False

    smtp_class = (
        smtplib.SMTP_SSL
        if "smtp_ssl" in os.environ.get("E3_ENABLE_FEATURE", "").split(",")
        else smtplib.SMTP
    )

    for smtp_server in smtp_servers:
        try:
            s = smtp_class(smtp_server)
        except (socket.error, smtplib.SMTPException) as e:
            logger.debug(e)
            logger.debug("cannot connect to smtp server %s", smtp_server)
            continue
        else:
            try:
                if not s.sendmail(from_email, to_emails, mail_as_string):
                    # sendmail returns an empty dictionary if the message
                    # was accepted for delivery to all addresses
                    break
                continue
            except (socket.error, smtplib.SMTPException) as e:
                logger.debug(e)
                logger.debug("smtp server error: %s", smtp_server)
                continue
            finally:
                try:
                    s.quit()
                    logger.debug("smtp quit")
                except (socket.error, smtplib.SMTPException):
                    # The message has already been delivered, ignore all errors
                    # when terminating the session.
                    pass

    else:
        logger.debug("no valid smtp server found")
        if not system_sendmail():
            return False

    if message_id is not None:
        logger.debug("Message-ID: %s sent successfully", message_id)

    return True
