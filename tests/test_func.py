import base64
import json
import pytest

import main
from cloud_build_status import credentials, provider
import cloud_build_status


def event(func):
    def wrapper():
        data = func()
        encoded = base64.b64encode(json.dumps(data).encode())
        return {'data': encoded}

    return wrapper


@pytest.fixture
@event
def github_data():
    return {
        'sourceProvenance': {
            'resolvedRepoSource': {
                'commitSha': 'd985a61daddbcd9c05a06d199efc2aeca55e4a19',
                'repoName': 'github_leg100_webapp'
            }
        },
        'logUrl': 'https://console.cloud.google.com/gcr/builds/aeccd2ef-f51a-4a44-8e2e-0de2609ce367?project=292927648743',
        'buildTriggerId': '2bceb582-3141-44bf-b444-5640cbcaecc5',
        'status': 'SUCCESS'
    }


@pytest.fixture
@event
def bitbucket_data():
    return {
        'sourceProvenance': {
            'resolvedRepoSource': {
                'commitSha': '65ca6a99a2573f0f1ff5dc93f78a77966248ea2d',
                'repoName': 'bitbucket_garman_webapp'
            }
        },
        'logUrl': 'https://console.cloud.google.com/gcr/builds/aeccd2ef-f51a-4a44-8e2e-0de2609ce367?project=292927648743',
        'buildTriggerId': '2bceb582-3141-44bf-b444-5640cbcaecc5',
        'status': 'SUCCESS'
    }


@pytest.fixture
@event
def github_app_data():
    return {
        "sourceProvenance": {
            "resolvedStorageSource": {
                 "bucket": "292927648743.cloudbuild-source.googleusercontent.com",
                 "object": "ff7f18ef55982750630698ebffed9469a2d294db-9d56424f-c12b-4f7c-923b-34b9a77fcdaf.tar.gz",
                 "generation": "1570110452499581"
             }
        }
    }


@pytest.fixture
def env_vars(monkeypatch):
    monkeypatch.setenv('CREDENTIALS_BUCKET', 'my-secrets-bucket')
    monkeypatch.setenv('KMS_CRYPTO_KEY_ID',
            'projects/my-project/locations/global/keyRings/secrets/cryptoKeys/build-status')


@pytest.fixture
def patches(mocker):
    mocker.patch('cloud_build_status.credentials.get_ciphertext')
    mocker.patch('cloud_build_status.credentials.decrypt')

    def mocked_requests_post(url, auth, json):
        class MockResponse:
            def __init__(self, status_code):
                self.status_code = status_code

        if url.startswith('https://api.github.com'):
            if auth[1] == 'password1':
                return MockResponse(201)
            else:
                return MockResponse(403)

        if url.startswith('https://api.bitbucket.org'):
            if auth[1] == '12345678':
                return MockResponse(201)
            else:
                return MockResponse(403)

    mocker.patch('requests.post', side_effect=mocked_requests_post)


def test_github(github_data, env_vars, mocker, patches):
    mocker.patch('cloud_build_status.credentials.get_ciphertext', return_value='FALKJFLKN')
    mocker.patch('cloud_build_status.credentials.decrypt',
            return_value='{"username":"leg100", "password":"password1"}')

    main.build_status(github_data, None)

    cloud_build_status.credentials.get_ciphertext.assert_called_once_with(
            'my-secrets-bucket',
            'github')

    cloud_build_status.credentials.decrypt.assert_called_once_with(
        'projects/my-project/locations/global/keyRings/secrets/cryptoKeys/build-status',
        'FALKJFLKN')

    provider.requests.post.assert_called_once_with(
        'https://api.github.com/repos/leg100/webapp/statuses/d985a61daddbcd9c05a06d199efc2aeca55e4a19',
        auth=('leg100', 'password1'),
        json={
            'description': 'SUCCESS',
            'state': 'success',
            'context': 'Google Cloud Build',
            'target_url': 'https://console.cloud.google.com/gcr/builds/aeccd2ef-f51a-4a44-8e2e-0de2609ce367?project=292927648743',
        })


def test_bitbucket(bitbucket_data, env_vars, mocker, patches):
    mocker.patch('cloud_build_status.credentials.get_ciphertext', return_value='FALKJFLKN')
    mocker.patch('cloud_build_status.credentials.decrypt',
            return_value='{"username":"lg", "password":"12345678"}')

    main.build_status(bitbucket_data, None)

    cloud_build_status.credentials.get_ciphertext.assert_called_once_with(
            'my-secrets-bucket',
            'bitbucket')

    cloud_build_status.credentials.decrypt.assert_called_once_with(
        'projects/my-project/locations/global/keyRings/secrets/cryptoKeys/build-status',
        'FALKJFLKN')

    provider.requests.post.assert_called_once_with(
        'https://api.bitbucket.org/2.0/repositories/garman/webapp/commit/65ca6a99a2573f0f1ff5dc93f78a77966248ea2d/statuses/build',
        auth=('lg', '12345678'),
        json={
            'description': 'SUCCESS',
            'state': 'SUCCESSFUL',
            'name': 'Google Cloud Build',
            'url': 'https://console.cloud.google.com/gcr/builds/aeccd2ef-f51a-4a44-8e2e-0de2609ce367?project=292927648743',
            'key': '2bceb582-3141-44bf-b444-5640cbcaecc5'
        })


def test_github_second_invocation(github_data, env_vars, patches):
    main.build_status(github_data, None)

    cloud_build_status.credentials.get_ciphertext.assert_not_called()
    cloud_build_status.credentials.decrypt.assert_not_called()


def test_bitbucket_second_invocation(bitbucket_data, env_vars, patches):
    main.build_status(bitbucket_data, None)

    cloud_build_status.credentials.get_ciphertext.assert_not_called()
    cloud_build_status.credentials.decrypt.assert_not_called()


def test_github_invalid_password(github_data, env_vars, mocker, patches):
    credentials.Credentials._data = {}

    mocker.patch('cloud_build_status.credentials.get_ciphertext', return_value='FALKJFLKN')
    mocker.patch('cloud_build_status.credentials.decrypt',
            return_value='{"username":"leg100", "password":"wrong_pass"}')

    with pytest.raises(RuntimeError, match="403"):
        main.build_status(github_data, None)

def test_ignore_event(github_app_data, env_vars, mocker, patches):
    main.build_status(github_app_data, None)

    provider.requests.post.assert_not_called()
