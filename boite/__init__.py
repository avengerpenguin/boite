class Boite(object):
    def __init__(self, server, inbox='INBOX'):
        self.server = server
        self.inbox = inbox

    def next_stuff(self):
        self.server.select_folder(self.inbox)
        oldest = self.server.sort(sort_criteria=['ARRIVAL'])[0]
        return oldest
