from __future__ import unicode_literals, print_function
import email
import os
import sys
import imapclient
from backports import ssl
from datetime import date
import logging


HOST = os.getenv('MAIL_HOST')
USERNAME = os.getenv('USER')
PASSWORD = os.getenv('PASSWORD')


LOG = logging.getLogger()
LOG.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stderr)
LOG.addHandler(handler)


def make_server():
    context = imapclient.create_default_context()

    # don't check if certificate hostname doesn't match target hostname
    context.check_hostname = False

    # don't check if the certificate is trusted by a certificate authority
    context.verify_mode = ssl.CERT_NONE

    LOG.info('Logging in to {host}...'.format(host=HOST))
    server = imapclient.IMAPClient(HOST, use_uid=True, ssl=True, ssl_context=context)
    server.login(USERNAME, PASSWORD)
    return server


def check_match(message, header, pattern):

    if header == 'Body':
        value = ''

        for m in (part for part in message.walk() if not part.is_multipart()):
            try:
                value = m.get_payload(decode=True)
                break
            except UnicodeEncodeError:
                print('UNICODE ERROR')
                m.set_charset('utf-8')
                value = m.get_payload(decode=True)
                break
            except KeyError:
                value = ''
                continue

        message = m
    else:
        value = message[header]

    #print('Using value: ' + repr(value))

    if type(value) == bytes:
        charset = message.get_charset()
        if charset:
            charset = charset.input_charset
        else:
            content_type = (message['Content-Type'] or '').lower()
            if 'iso-8859-1' in content_type:
                charset = 'iso-8859-1'
            elif 'windows-1252' in content_type:
                charset = 'windows-1252'
            else:
                charset = 'utf-8'
        value = value.decode(charset, errors='replace')

    try:
        return pattern.match(value or '')
    except AttributeError:
        return value == pattern


def archive_stale(matchers, age):
    cutoff = date.today() - age
    server = make_server()

    LOG.info('Opening INBOX')
    server.select_folder('INBOX')

    LOG.info('Looking at messages from before {cutoff}'.format(cutoff=cutoff))
    message_ids = server.search(criteria=['BEFORE', cutoff])
    messages = server.fetch(message_ids, ['INTERNALDATE', 'RFC822', 'UID'])

    for uid, raw_message in messages.items():
        print('.', file=sys.stderr, end='')
        sys.stderr.flush()
        if b'RFC822' not in raw_message:
            LOG.error('Weird message: ' + str(raw_message))
            continue
        message = email.message_from_bytes(raw_message[b'RFC822'])

        for matcher in matchers:
            matches = sum([1 for header, pattern in matcher.items() if check_match(message, header, pattern)])

            if matches == len(matcher):
                print('.', file=sys.stderr)
                LOG.info('Archiving message with subject "{subject}" as '
                         'it matches {matcher}'.format(
                    subject=message['Subject'], matcher=matcher))

                server.copy([uid], 'archive')
                server.delete_messages([uid])
                server.expunge()
                continue

    print('.', file=sys.stderr)


def mark_spam(matchers):
    server = make_server()

    LOG.info('Opening INBOX')
    server.select_folder('INBOX')

    LOG.info('Scanning all messages for spam...')

    message_ids = server.search()
    messages = server.fetch(message_ids, ['INTERNALDATE', 'RFC822', 'UID'])

    for uid, raw_message in messages.items():
        print('.', file=sys.stderr, end='')
        sys.stderr.flush()
        if b'RFC822' not in raw_message:
            LOG.error('Weird message: ' + str(raw_message))
            continue
        message = email.message_from_bytes(raw_message[b'RFC822'] or b'')

        for matcher in matchers:
            try:
                matches = sum([1 for header, pattern in matcher.items() if check_match(message, header, pattern)])
            except Exception as e:
                print('Error {e} processing message: {message}'.format(e=e, message=repr(message.as_bytes())))
                sys.exit(1)

            if matches == len(matcher):
                print('.', file=sys.stderr)
                LOG.info('Marking as spam message with subject "{subject}" as it '
                         'matches {matcher}'.format(
                    subject=message['Subject'], matcher=matcher))

                server.copy([uid], 'spam')
                server.delete_messages([uid])
                server.expunge()
                break

    print('.', file=sys.stderr)


class Boite(object):
    def __init__(self, server, inbox='INBOX'):
        self.server = server
        self.inbox = inbox

    def next_stuff(self):
        self.server.select_folder(self.inbox)
        oldest = self.server.sort(sort_criteria=['ARRIVAL'])[0]
        message = self.server.fetch([oldest], ['INTERNALDATE', 'RFC822', 'UID'])[oldest]
        return Stuff(oldest, message)

    def archive(self, stuff):
        stuff.archive(self.server)


class Stuff(object):
    def __init__(self, uid, message):
        self.raw_message = message
        self.message = email.message_from_bytes(self.raw_message[b'RFC822'])
        self.uid = uid

    def __str__(self):
        if (self.message.is_multipart()):
            return self.message.get_payload(0).as_string()
        else:
            return self.message.get_payload().as_string()

    def archive(self, server):
        # TODO: Remove hard-coding
        print(self.raw_message.keys())
        print(self.raw_message[b'SEQ'])
        server.copy([self.uid], 'archive')
        server.delete_messages([self.uid])
        server.expunge()
