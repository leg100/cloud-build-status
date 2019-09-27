# bitbucket-build-status

Update Bitbucket build status with the results of a Google Cloud Build pipeline.

## Requirements

* Bitbucket Cloud (not Bitbucket *Server*!) repository
* Google Cloud project

## Summary

There is currently no built-in integration between Bitbucket and Google Cloud Build. Google Cloud does provide for mirroring a Bitbucket repository to a Google Cloud Source Repository. And then a Cloud Build trigger can be configured to run a build whenever commits are pushed. However, there is no built-in support for reporting the build status back to the Bitbucket repository. 

`bitbucket-build-status` provides a Google Cloud Function to perform this last step. Cloud Build sends events detailing progress of a build to  the `cloud-builds` Google PubSub topic. The Cloud Function subscribes to the topic, and propagates these events to Bitbucket, resulting an [icon against the commit or the pull request](https://confluence.atlassian.com/bitbucket/integrate-your-build-system-with-bitbucket-cloud-790790968.html) showing whether the build is progressing, or has succeeded or failed, along with a link to the relevant Cloud Build build logs.

## Design

I've done my best to design the function according to best practices:

* Assign it permissions according to principle of least privilege
* Lazily load and reuse computationally expensive code paths
* Keep credentials encrypted, and decrypt only on first use
* Unit tested (although no integration tests)

I got a lot of help from reading Seth Vargo's [Secrets in Serverless blog post](https://www.sethvargo.com/secrets-in-serverless). In choosing to both encrypt the credentials with KMS and store the resulting ciphertext on cloud storage (and having the function retrieve and decrypt them at run-time), the credentials can be rotated at any time without having to re-deploy the function.

## Installation

### Setup Cloud Build

Follow these [instructions](https://cloud.google.com/cloud-build/docs/running-builds/automate-builds). Once you've done so, you'll have:

  * A Bitbucket repository mirrored to Cloud Source Repositories
  * A Cloud Build config file (e.g. `cloudbuild.yaml`) in the repository
  * A Cloud Build trigger to run a build when a commit is pushed
  
Make a note of the Google Cloud project you decide to use. From hereon in, all resources are configured in the context of this project.

### Setup Bitbucket Credentials

Nominate a Bitbucket account for Cloud Function to authenticate with the Bitbucket API. This need not be the same account as that used for mirroring the repository in the previous step.

Create an [app password](https://confluence.atlassian.com/bitbucket/app-passwords-828781300.html) for that account.

Assign to the app password the `repository:write` scope. (I think this is the minimum necessary permission for Bitbucket to update the build status...).

Keep a note of the username and password for later.

### Enable Google Cloud APIs

If you have not previously used Cloud Functions, Cloud KMS, or Cloud Storage, enable the APIs on your Google Cloud Project:

```bash
gcloud services enable \
  cloudfunctions.googleapis.com \
  kms.googleapis.com \
  storage-component.googleapis.com
```

### Create KMS keys

Create KMS keyring and key:

```bash
gcloud kms keyrings create bb-secrets --location global

gcloud kms keys create build-status \
  --location global \
  --keyring bb-secrets \
  --purpose encryption
```

### Create Storage Bucket

Create Google Cloud Storage bucket in which to store encrypted credentials (the ciphertext):

```bash
gsutil mb gs://bb-secrets/
```

### Upload Credentials

Encrypt the username and app password you created earlier, and upload the resulting ciphertext to the bucket:

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

Note: this step can be repeated whenever you want to rotate the credentials.

### Configure IAM

Create a new service account for use by the Cloud Function:

```bash
gcloud iam service-accounts create bb-kms-decrypter
```

Grant permissions to read the ciphertext from the bucket. Be sure to replace `${GOOGLE_CLOUD_PROJECT}` with your project name:

```bash
gsutil iam ch serviceAccount:bb-kms-decrypter@${GOOGLE_CLOUD_PROJECT}.iam.gserviceaccount.com:legacyBucketReader \
    gs://bb-secrets

gsutil iam ch serviceAccount:bb-kms-decrypter@${GOOGLE_CLOUD_PROJECT}.iam.gserviceaccount.com:legacyObjectReader \
    gs://bb-secrets/build-status
```

Grant the most minimal set of permissions to decrypt data using the KMS key created above. Be sure to replace `${GOOGLE_CLOUD_PROJECT}` with your project name.

```bash
gcloud kms keys add-iam-policy-binding build-status \
    --location global \
    --keyring bb-secrets \
    --member "serviceAccount:bb-kms-decrypter@${GOOGLE_CLOUD_PROJECT}.iam.gserviceaccount.com" \
    --role roles/cloudkms.cryptoKeyDecrypter
```

The function now has the permissions to both read the ciphertext from the bucket as well as to decrypt the ciphertext.

### Deploy

Deploy the function. Be sure to replace `${GOOGLE_CLOUD_PROJECT}` with your project name.

```bash
$ gcloud beta functions deploy encrypted-envvars \
    --source ./python \
    --runtime python37 \
    --entry-point build_status \
    --service-account bb-kms-decrypter@${GOOGLE_CLOUD_PROJECT}.iam.gserviceaccount.com \
    --set-env-vars KMS_CRYPTO_KEY_ID=projects/${GOOGLE_CLOUD_PROJECT}/locations/global/keyRings/bb-secrets/cryptoKeys/bb-secrets,SECRETS_BUCKET=bb-secrets,SECRETS_OBJECT=build-status \
    --trigger-topic=cloud-builds
```

### Test

Everything is now in place. To test that it's working, push a commit to the Bitbucket repository and confirm that a build status icon appears next to the commit.
