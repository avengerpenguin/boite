import email
from email.parser import BytesParser


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
