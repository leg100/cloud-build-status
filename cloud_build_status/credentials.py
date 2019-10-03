from google.cloud import kms_v1, storage, exceptions
import json
import os


def get_ciphertext(bucket_name, obj):
    client = storage.Client()

    try:
        bucket = client.get_bucket(bucket_name)
    except exceptions.NotFound:
        raise RuntimeError(f"Could not find bucket {bucket_name}")

    blob = bucket.get_blob(obj)
    if blob is None:
        raise RuntimeError(f"Could not find object {obj} in bucket {bucket_name}")

    return blob.download_as_string()


def decrypt(crypto_key_id, ciphertext):
    return kms_v1 \
        .KeyManagementServiceClient() \
        .decrypt(crypto_key_id, ciphertext) \
        .plaintext \
        .decode('utf-8') \
        .strip()


class Credentials:
    _data = {}

    @classmethod
    def get(cls, provider):
        if provider.__name__ not in cls._data:
            crypto_key_id = os.environ['KMS_CRYPTO_KEY_ID']
            bucket = os.environ['CREDENTIALS_BUCKET']
            obj = provider.__name__.lower()

            ciphertext = get_ciphertext(bucket, obj)
            plaintext = decrypt(crypto_key_id, ciphertext)

            cls._data[provider.__name__] = json.loads(plaintext)

        creds = cls._data[provider.__name__]

        return (creds['username'], creds['password'])
