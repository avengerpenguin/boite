import os
import clize
import cmd
import imapclient
from backports import ssl
from boite import Boite


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


class StuffShell(cmd.Cmd):
    intro = 'Stuff processing'
    prompt = '> '

    def __init__(self):
        super().__init__()
        self.server = make_server()
        self.boite = Boite(self.server)

    def do_done(self, _):
        """
        Quits.
        """
        print('Bye!')
        return True

    do_bye = do_done
    do_quit = do_done

    def do_next(self, arg):
        self.next = self.boite.next_stuff()
        print(self.next)
        print('Now run either "archive (a)", "spam (s)", "todo (t)"')

    def do_archive(self, _):
        self.boite.archive(self.next)


def stuff():
    StuffShell().cmdloop()


def main():
    clize.run(stuff)
