from __future__ import unicode_literals, print_function
import imapclient
from backports import ssl

from fixture_proxy import ImapProxy

HOST = 'mail.rossfenning.co.uk'
USERNAME = 'post@rossfenning.co.uk'
PASSWORD = 'c4ffr3y5'


def test():
    context = imapclient.create_default_context()

    # don't check if certificate hostname doesn't match target hostname
    context.check_hostname = False

    # don't check if the certificate is trusted by a certificate authority
    context.verify_mode = ssl.CERT_NONE

    server = ImapProxy(imapclient.IMAPClient(HOST, use_uid=True, ssl=True, ssl_context=context))
    server.login(USERNAME, PASSWORD)

    stuff = server.folder_status('INBOX', ('MESSAGES'))[b'MESSAGES']

    assert stuff == 0