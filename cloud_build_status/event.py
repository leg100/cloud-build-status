import base64
import json


class Event:
    def __init__(self, event):
        decoded = base64.b64decode(event['data']).decode('utf-8')
        self.data = json.loads(decoded)


    @property
    def state(self):
        return self.data['status']


    @property
    def commit(self):
        return self.data['sourceProvenance']['resolvedRepoSource']['commitSha']


    @property
    def mirror(self):
        return self.data['sourceProvenance']['resolvedRepoSource']['repoName']


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
