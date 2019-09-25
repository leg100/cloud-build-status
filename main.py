import json
import os

from google.cloud import kms_v1, storage


encrypted_creds = None
username = None
password = None


def get_encrypted_creds(bucket, obj):
    return storage.Client() \
        .get_bucket(bucket) \
        .get_blob(obj) \
        .download_as_string()


def decrypt(crypto_key_id, ciphertext):
    response = kms_v1 \
        .KeyManagementServiceClient() \
        .decrypt(crypto_key_id, ciphertext)

    return base64.b64decode(response['plaintext']).decode('utf-8').strip()


def bb_req(url, username, password, payload):
    resp = requests.post(url, auth=(username, password), json=payload)

    return resp.status_code


def build_url(owner, repo_slug, revision):
    return ('https://api.bitbucket.org/2.0/repositories/'
           f'{owner}/{repo_slug}/commit/{revision}/statuses/build')


def build_status(event, context):
    """
    Background Cloud Function to be triggered by Pub/Sub.

    Updates Bitbucket Cloud repository build status. Triggered by incoming
    pubsub messages from Google Cloud Build.

    Args:
         event (dict):  The dictionary with data specific to this type of
         event. The `data` field contains the PubsubMessage message. The
         `attributes` field will contain custom attributes if there are any.
         context (google.cloud.functions.Context): The Cloud Functions event
         metadata. The `event_id` field contains the Pub/Sub message ID. The
         `timestamp` field contains the publish time.
    """
    import base64
    import requests

    secrets_bucket = os.environ['SECRETS_BUCKET']
    secrets_obj = os.environ['SECRETS_OBJECT']
    crypto_key_id = os.environ['KMS_CRYPTO_KEY_ID']

    global encrypted_creds, username, password

    if not encrypted_creds:
        json_string = get_encrypted_creds(secrets_bucket, secrets_obj)
        encrypted_creds = json.loads(json_string)

    if not username:
        username = decrypt(crypto_key_id, encrypted_creds['username'])

    if not password:
        password = decrypt(crypto_key_id, encrypted_creds['password'])


    data = base64.b64decode(event['data']).decode('utf-8')
    msg = json.loads(data)

    status = msg['status']
    commit_sha = msg['sourceProvenance']['resolvedRepoSource']['commitSha']
    mirror = msg['sourceProvenance']['resolvedRepoSource']['repoName']

    # mirror looks like: bitbucket_<user>_<repo>
    # it permits underscores in <repo>, but assumes <user> does not
    _, bb_user, bb_repo = mirror.split('_', 2)

    bb_states = {
        'SUCCESS': 'SUCCESSFUL',
        'QUEUED': 'INPROGRESS',
        'WORKING': 'INPROGRESS'
        }

    payload = {
            'description': status,
            'state': bb_states.get(status, 'FAILED'),
            'name': 'Google Cloud Build',
            'url': msg['logUrl'],
            'key': msg['buildTriggerId']
            }

    api_url = build_url(bb_user, bb_repo, commit_sha)

    return bb_req(api_url, username, password, payload) == 200
