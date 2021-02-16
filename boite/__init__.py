import email
import logging
import os
# from backports import ssl
import ssl
import sys
from datetime import date

import imapclient
from progressbar import ETA, Bar, Percentage, ProgressBar

HOST = os.getenv("MAIL_HOST")
USERNAME = os.getenv("USER")
PASSWORD = os.getenv("PASSWORD")


LOG = logging.getLogger()
LOG.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stderr)
LOG.addHandler(handler)


def query_yes_no(question, default="no"):
    """Ask a yes/no question via raw_input() and return their answer.

    "question" is a string that is presented to the user.
    "default" is the presumed answer if the user just hits <Enter>.
        It must be "yes" (the default), "no" or None (meaning
        an answer is required of the user).

    The "answer" return value is True for "yes" or False for "no".
    """
    valid = {"yes": True, "y": True, "ye": True, "no": False, "n": False}
    if default is None:
        prompt = " [y/n] "
    elif default == "yes":
        prompt = " [Y/n] "
    elif default == "no":
        prompt = " [y/N] "
    else:
        raise ValueError("invalid default answer: '%s'" % default)

    while True:
        sys.stdout.write(question + prompt)
        choice = input().lower()
        if default is not None and choice == "":
            return valid[default]
        elif choice in valid:
            return valid[choice]
        else:
            sys.stdout.write("Please respond with 'yes' or 'no' " "(or 'y' or 'n').\n")


def create_default_context():
    return ssl.create_default_context()


def IMAP(
    host, port=None, user=None, password=None, use_uid=True, ssl=True, ssl_context=None
):
    server = imapclient.IMAPClient(
        host, port=port, use_uid=use_uid, ssl=ssl, ssl_context=ssl_context
    )
    server.login(user, password)
    return server


def make_server():
    context = imapclient.create_default_context()

    # don't check if certificate hostname doesn't match target hostname
    context.check_hostname = False

    # don't check if the certificate is trusted by a certificate authority
    context.verify_mode = ssl.CERT_NONE

    LOG.info(f"Logging in to {HOST}...")
    server = imapclient.IMAPClient(HOST, use_uid=True, ssl=True, ssl_context=context)
    server.login(USERNAME, PASSWORD)
    return server


def check_match(message, header, pattern):

    if header == "Body":
        value = ""

        for m in (part for part in message.walk() if not part.is_multipart()):
            try:
                value = m.get_payload(decode=True)
                break
            except UnicodeEncodeError:
                print("UNICODE ERROR")
                m.set_charset("utf-8")
                value = m.get_payload(decode=True)
                break
            except KeyError:
                value = ""
                continue

        message = m
    else:
        value = message[header]

    if type(value) == bytes:
        charset = message.get_charset()
        if charset:
            charset = charset.input_charset
        else:
            content_type = (message["Content-Type"] or "").lower()
            if "iso-8859-1" in content_type:
                charset = "iso-8859-1"
            elif "windows-1252" in content_type:
                charset = "windows-1252"
            else:
                charset = "utf-8"
        value = value.decode(charset, errors="replace")

    try:
        return pattern.match(str(value) or "")
    except AttributeError:
        return value == pattern


def archive_stale(server, matchers, age, folder=None):
    cutoff = date.today() - age

    if not folder:
        folder = "archive"

    LOG.info("Opening INBOX")
    server.select_folder("INBOX")

    LOG.info(f"Looking at messages from before {cutoff}")
    message_ids = server.search(criteria=["BEFORE", cutoff])

    LOG.info("Found {count} messages to check".format(count=len(message_ids)))
    pbar = ProgressBar(widgets=[ETA(), Percentage(), Bar()])
    for message_id in pbar(message_ids):

        messages = server.fetch(
            [message_id], ["INTERNALDATE", "RFC822", "UID", "ENVELOPE"]
        )

        for uid, raw_message in messages.items():
            sys.stderr.flush()

            if b"RFC822" not in raw_message and b"BODY[NULL]" not in raw_message:
                LOG.error("Weird message: " + str(raw_message))
                continue
            if b"RFC822" in raw_message:
                message = email.message_from_bytes(raw_message[b"RFC822"])
            else:
                message = email.message_from_bytes(raw_message[b"BODY[NULL]"])

            for matcher in matchers:
                matches = sum(
                    [
                        1
                        for header, pattern in matcher.items()
                        if check_match(message, header, pattern)
                    ]
                )

                if matches == len(matcher):
                    LOG.info(
                        'Archiving message with subject "{subject}" as '
                        "it matches {matcher}".format(
                            subject=message["Subject"], matcher=matcher
                        )
                    )

                    if callable(folder):
                        server.copy([uid], folder(raw_message))
                    else:
                        server.copy([uid], folder)
                    server.delete_messages([uid])
                    break

    server.expunge()


def mark_spam(server, matchers):
    LOG.info("Opening INBOX")
    server.select_folder("INBOX")

    LOG.info("Scanning all messages for spam...")

    message_ids = server.search()

    LOG.info("Found {count} messages to check".format(count=len(message_ids)))
    pbar = ProgressBar(widgets=[ETA(), Percentage(), Bar()])
    for message_id in pbar(message_ids):

        messages = server.fetch(
            [message_id], ["INTERNALDATE", "RFC822", "UID", "ENVELOPE"]
        )

        for uid, raw_message in messages.items():
            # print('.', file=sys.stderr, end='')
            sys.stderr.flush()
            if b"RFC822" not in raw_message:
                LOG.error("Weird message: " + str(raw_message))
                continue
            message = email.message_from_bytes(raw_message[b"RFC822"] or b"")

            for matcher in matchers:
                try:
                    matches = sum(
                        [
                            1
                            for header, pattern in matcher.items()
                            if check_match(message, header, pattern)
                        ]
                    )
                except Exception as e:
                    print(
                        "Error {e} processing message: {message}".format(
                            e=e, message=repr(message.as_bytes())
                        )
                    )
                    sys.exit(1)

                if matches == len(matcher):
                    # print('.', file=sys.stderr)
                    LOG.info(
                        'Marking as spam message with subject "{subject}" as it '
                        "matches {matcher}".format(
                            subject=message["Subject"], matcher=matcher
                        )
                    )

                    server.copy([uid], "spam")
                    server.delete_messages([uid])
                    break

    server.expunge()
    # print('.', file=sys.stderr)


class Message:
    def __init__(self, server, uid, message):
        self.server = server
        self.uid = uid
        self.message = message

    @property
    def headers(self):
        return dict(self.message)

    @property
    def body(self):
        value = ""

        for m in (part for part in self.message.walk() if not part.is_multipart()):
            try:
                value = m.get_payload(decode=True)
                break
            except UnicodeEncodeError:
                print("UNICODE ERROR")
                m.set_charset("utf-8")
                value = m.get_payload(decode=True)
                break
            except KeyError:
                value = ""
                continue

        return value

    def archive(self, folder=None):
        LOG.info(f"Archiving {self.uid}")
        self.server.copy([self.uid], folder or "archive")
        self.server.delete_messages([self.uid])
        self.server.expunge()

    def mark_spam(self):
        self.server.copy([self.uid], "spam")
        self.server.delete_messages([self.uid])
        self.server.expunge()


def stream(server, matchers, age=None):
    LOG.info("Opening INBOX")
    server.select_folder("INBOX")

    LOG.info("Scanning all messages for custom processing...")

    if age:
        cutoff = date.today() - age
        LOG.info(f"Looking at messages from before {cutoff}")
        message_ids = server.search(criteria=["BEFORE", cutoff])
        messages = server.fetch(message_ids, ["INTERNALDATE", "RFC822", "UID"])
    else:
        message_ids = server.search()
        messages = server.fetch(message_ids, ["INTERNALDATE", "RFC822", "UID"])

    for uid, raw_message in messages.items():
        print(".", file=sys.stderr, end="")
        sys.stderr.flush()

        if b"RFC822" not in raw_message and b"BODY[NULL]" not in raw_message:
            LOG.error("Weird message: " + str(raw_message))
            LOG.error(raw_message.keys())
            continue
        message = email.message_from_bytes(
            raw_message.get(b"RFC822", raw_message.get(b"BODY[NULL]", b""))
        )

        for matcher in matchers:
            try:
                matches = sum(
                    [
                        1
                        for header, pattern in matcher.items()
                        if check_match(message, header, pattern)
                    ]
                )
            except Exception as e:
                print(
                    "Error {e} processing message: {message}".format(
                        e=e, message=repr(message.as_bytes())
                    )
                )
                sys.exit(1)

            if matches == len(matcher):
                print(".", file=sys.stderr)
                # LOG.info('Doing custom action to message with subject '
                #          '"{subject}" as it matches {matcher}'.format(
                #     subject=message['Subject'], matcher=matcher))

                yield Message(server, uid, message)
                break

    print(".", file=sys.stderr)


class Boite:
    def __init__(self, server, inbox="INBOX"):
        self.server = server
        self.inbox = inbox

    def next_stuff(self):
        self.server.select_folder(self.inbox)
        oldest = self.server.sort(sort_criteria=["ARRIVAL"])[0]
        message = self.server.fetch([oldest], ["INTERNALDATE", "RFC822", "UID"])[oldest]
        return Stuff(oldest, message)

    def archive(self, stuff):
        stuff.archive(self.server)


class Stuff:
    def __init__(self, uid, message):
        self.raw_message = message
        self.message = email.message_from_bytes(self.raw_message[b"RFC822"])
        self.uid = uid

    def __str__(self):
        if self.message.is_multipart():
            return self.message.get_payload(0).as_string()
        else:
            return self.message.get_payload().as_string()

    def archive(self, server):
        # TODO: Remove hard-coding
        print(self.raw_message.keys())
        print(self.raw_message[b"SEQ"])
        server.copy([self.uid], "archive")
        server.delete_messages([self.uid])
        server.expunge()
