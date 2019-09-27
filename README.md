# bitbucket-build-status

Update Bitbucket build status with the results of a Google Cloud Build pipeline.

## Requirements

* Bitbucket Cloud (not Bitbucket *Server*!) repository
* Google Cloud project

## Summary

There is currently no built-in integration between Bitbucket and Google Cloud Build. Google Cloud does provide for mirroring a Bitbucket repository to a Google Cloud Source Repository. And then a Cloud Build trigger can be configured to run a build whenever commits are pushed. However, there is no built-in support for reporting the build status back to the Bitbucket repository. 

`bitbucket-build-status` provides a Google Cloud Function to perform this last step. Cloud Build sends events detailing progress of a build to  the `cloud-builds` Google PubSub topic. The Cloud Function subscribes to the topic, and propagates these events to Bitbucket, resulting an [icon against the commit or the pull request](https://confluence.atlassian.com/bitbucket/integrate-your-build-system-with-bitbucket-cloud-790790968.html) showing whether the build is progressing, or has succeeded or failed, along with a link to the relevant Cloud Build build logs.

## Installation

Mirror your Bitbucket repository to Cloud Source Repositories by following [these instructions](https://cloud.google.com/source-repositories/docs/mirroring-a-bitbucket-repository).

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
