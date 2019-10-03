import requests

from cloud_build_status.credentials import Credentials


class Provider:
    def __init__(self, event):
        self.event = event


    def send_status(self):
        resp = requests.post(
                self.url,
                auth=Credentials.get(self.__class__),
                json=self.payload)

        if resp.status_code not in [200, 201]:
            raise RuntimeError(f"HTTP {resp.status_code} response from POST {self.url}")


    @property
    def state(self):
        return self.states[self.event.state]


    @staticmethod
    def create_from_event(event):
        klass = globals()[event.provider.capitalize()]

        return klass(event)


class Github(Provider):
    states = {
        'STATUS_UNKNOWN' : 'pending',
        'QUEUED'         : 'pending',
        'WORKING'        : 'pending',
        'SUCCESS'        : 'success',
        'FAILURE'        : 'failure',
        'CANCELLED'      : 'failure',
        'INTERNAL_ERROR' : 'error',
        'TIMEOUT'        : 'error'
        }


    @property
    def url(self):
        return ('https://api.github.com/'
            f'repos/{self.event.owner}/{self.event.repo}'
            f'/statuses/{self.event.commit}')


    @property
    def payload(self):
        return {
            'description': self.event.state,
            'state': self.state,
            'context': 'Google Cloud Build',
            'target_url': self.event.url
            }


class Bitbucket(Provider):
    states = {
        'STATUS_UNKNOWN' : 'INPROGRESS',
        'QUEUED'         : 'INPROGRESS',
        'WORKING'        : 'INPROGRESS',
        'SUCCESS'        : 'SUCCESSFUL',
        'FAILURE'        : 'FAILED',
        'CANCELLED'      : 'FAILED',
        'INTERNAL_ERROR' : 'STOPPED',
        'TIMEOUT'        : 'STOPPED'
        }


    @property
    def url(self):
        return ('https://api.bitbucket.org/'
            f'2.0/repositories/{self.event.owner}/{self.event.repo}'
            f'/commit/{self.event.commit}/statuses/build')


    @property
    def payload(self):
        return {
            'description': self.event.state,
            'state': self.state,
            'name': 'Google Cloud Build',
            'url': self.event.url,
            'key': self.event.build_trigger_id,
            }
