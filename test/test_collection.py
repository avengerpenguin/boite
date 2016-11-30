from __future__ import unicode_literals, print_function
import os
import imapclient
from backports import ssl
from fixture_proxy import ImapProxy
from boite import Boite
import pytest


HOST = os.getenv('MAIL_HOST')
USERNAME = os.getenv('USER')
PASSWORD = os.getenv('PASSWORD')


@pytest.fixture
def server():
    context = imapclient.create_default_context()

    # don't check if certificate hostname doesn't match target hostname
    context.check_hostname = False

    # don't check if the certificate is trusted by a certificate authority
    context.verify_mode = ssl.CERT_NONE

    server = ImapProxy(
        imapclient.IMAPClient(HOST, use_uid=True, ssl=True, ssl_context=context)
    )
    server.login(USERNAME, PASSWORD)
    return server


def test_get_stuff(server):
    boite = Boite(server)
    next = boite.next_stuff()
    assert next
