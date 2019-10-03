import base64
import json


class IrrelevantEvent(Exception):
    pass


class Event:
    def __init__(self, event):
        decoded = base64.b64decode(event['data']).decode('utf-8')
        self.data = json.loads(decoded)


    @property
    def state(self):
        return self.data['status']


    @property
    def resolved_repo_source(self):
        try:
            return self.data['sourceProvenance']['resolvedRepoSource']
        except KeyError:
            raise IrrelevantEvent


    @property
    def commit(self):
        return self.resolved_repo_source['commitSha']


    @property
    def mirror(self):
        return self.resolved_repo_source['repoName']


    @property
    def provider(self):
        return self.mirror.split('_')[0]


    @property
    def owner(self):
        return self.mirror.split('_')[1]


    @property
    def repo(self):
        return self.mirror.split('_', 2)[-1]


    @property
    def url(self):
        return self.data['logUrl']


    @property
    def build_trigger_id(self):
        return self.data['buildTriggerId']
