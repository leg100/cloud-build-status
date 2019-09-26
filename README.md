# bitbucket-cloud-build-status
A Google Cloud Function that reports the status of a Google Cloud Build to Bitbucket Cloud.

If you have not previously used cloud functions or cloud storage, enable the APIs:

```bash
gcloud services enable \
  cloudfunctions.googleapis.com \
  storage-component.googleapis.com
```

Create KMS keyring and key:

```bash
gcloud kms keyrings create bb-secrets --location global

gcloud kms keys create build-status \
  --location global \
  --keyring bb-secrets \
  --purpose encryption
```

Create bucket in which to store encrypted credentials (the ciphertext):

```bash
gsutil mb gs://bb-secrets/
```

Encrypt your credentials and upload the ciphertext to the GCS bucket:

```bash
echo '{"username": "bb_user", "password": "*******"}' | \
  gcloud kms encrypt \
  --location global \
  --keyring=bb-secrets \
  --key=build-status \
  --ciphertext-file=- \
  --plaintext-file=- |
  gsutil cp - gs://bb-secrets/build-status
```

Create a new service account:

```bash
gcloud iam service-accounts create bb-kms-decrypter
```

Grant permissions to read the ciphertext from the bucket. Be sure to replace `GOOGLE_CLOUD_PROJECT` with your project name:

```bash
gsutil iam ch serviceAccount:bb-kms-decrypter@${GOOGLE_CLOUD_PROJECT}.iam.gserviceaccount.com:legacyBucketReader \
    gs://bb-secrets

gsutil iam ch serviceAccount:bb-kms-decrypter@${GOOGLE_CLOUD_PROJECT}.iam.gserviceaccount.com:legacyObjectReader \
    gs://bb-secrets/build-status
```

Grant the most minimal set of permissions to decrypt data using the KMS key created above. Be sure to replace `GOOGLE_CLOUD_PROJECT` with your project name.

```bash
gcloud kms keys add-iam-policy-binding build-status \
    --location global \
    --keyring bb-secrets \
    --member "serviceAccount:bb-kms-decrypter@${GOOGLE_CLOUD_PROJECT}.iam.gserviceaccount.com" \
    --role roles/cloudkms.cryptoKeyDecrypter
```

Deploy the function. Be sure to replace `GOOGLE_CLOUD_PROJECT` with your project name.

```bash
$ gcloud beta functions deploy encrypted-envvars \
    --source ./python \
    --runtime python37 \
    --entry-point build_status \
    --service-account bb-kms-decrypter@${GOOGLE_CLOUD_PROJECT}.iam.gserviceaccount.com \
    --set-env-vars KMS_CRYPTO_KEY_ID=projects/${GOOGLE_CLOUD_PROJECT}/locations/global/keyRings/bb-secrets/cryptoKeys/bb-secrets,SECRETS_BUCKET=bb-secrets,SECRETS_OBJECT=build-status \
    --trigger-topic=cloud-builds
```
