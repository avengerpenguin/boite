from __future__ import unicode_literals, print_function
import email
import os
from email.parser import BytesParser
import imapclient
from backports import ssl
from datetime import date

HOST = os.getenv('MAIL_HOST')
USERNAME = os.getenv('USER')
PASSWORD = os.getenv('PASSWORD')


def make_server():
    context = imapclient.create_default_context()

    # don't check if certificate hostname doesn't match target hostname
    context.check_hostname = False

    # don't check if the certificate is trusted by a certificate authority
    context.verify_mode = ssl.CERT_NONE

    server = imapclient.IMAPClient(HOST, use_uid=True, ssl=True, ssl_context=context)
    server.login(USERNAME, PASSWORD)
    return server


def archive_stale(matchers, age):
    cutoff = date.today() - age
    server = make_server()
    server.select_folder('INBOX')
    message_ids = server.search(criteria=['BEFORE', cutoff])
    messages = server.fetch(message_ids, ['INTERNALDATE', 'RFC822', 'UID'])
    for uid, raw_message in messages.items():
        message = email.message_from_bytes(raw_message[b'RFC822'])
        for matcher in matchers:
            matches = sum([1 for header, pattern in matcher.items() if message[header] == pattern])
            if matches == len(matcher):
                server.copy([uid], 'archive')
                server.delete_messages([uid])
                server.expunge()


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
