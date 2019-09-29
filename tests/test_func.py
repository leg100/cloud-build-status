import base64
from unittest import mock
import pytest

import main

@pytest.fixture
def event():
    event_json = open('tests/event_data.json', 'r').read()
    encoded = base64.b64encode(event_json.encode())
    return {'data': encoded}


@pytest.fixture
def env_vars(monkeypatch):
    monkeypatch.setenv('SECRETS_BUCKET', 'my-secrets-bucket')
    monkeypatch.setenv('SECRETS_OBJECT', 'bitbucket-creds')
    monkeypatch.setenv('KMS_CRYPTO_KEY_ID',
            'projects/my-project/locations/global/keyRings/secrets/cryptoKeys/bitbucket')

@pytest.fixture
def patches(mocker):
    mocker.patch('main.get_encrypted_creds', return_value='FALKJFLKN')
    mocker.patch('main.decrypt',
            return_value='{"username":"lg", "password":"12345678"}')
    mocker.patch('main.bb_req', return_value=200)


def test_func(event, env_vars, patches):
    assert main.build_status(event, None) == "OK"

    main.get_encrypted_creds.assert_called_once_with(
            'my-secrets-bucket',
            'bitbucket-creds')

    main.decrypt.assert_called_once_with(
        'projects/my-project/locations/global/keyRings/secrets/cryptoKeys/bitbucket',
        'FALKJFLKN')


def test_func_second_invocation(event, env_vars, patches):
    assert main.build_status(event, None) == "OK"

    main.get_encrypted_creds.assert_not_called()
    main.decrypt.assert_not_called()

    main.bb_req.assert_called_once_with(
        'https://api.bitbucket.org/2.0/repositories/garman/webapp/commit/65ca6a99a2573f0f1ff5dc93f78a77966248ea2d/statuses/build',
        'lg',
        '12345678',
        {
            'description': 'SUCCESS',
            'state': 'SUCCESSFUL',
            'name': 'Google Cloud Build',
            'url': 'https://console.cloud.google.com/gcr/builds/aeccd2ef-f51a-4a44-8e2e-0de2609ce367?project=292927648743',
            'key': '2bceb582-3141-44bf-b444-5640cbcaecc5'
        })


def test_func_bad_response(event, env_vars, mocker, patches):
    mocker.patch('main.bb_req', return_value=404)

    with pytest.raises(RuntimeError, match="404"):
        main.build_status(event, None)
