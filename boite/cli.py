import os
import clize
import cmd
import imapclient
from backports import ssl
from boite import Boite, make_server


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
