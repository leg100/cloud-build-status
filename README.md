# cloud-build-status

![Cloud Build](https://storage.googleapis.com/louis-garman-ci-badges/builds/cloud-build-status/branches/master.svg)

Integrate your repository's status checks with Google Cloud Build.

## Requirements

* Github or Bitbucket Cloud
* Google Cloud

## Summary

Google Cloud Build integrates with Github and Bitbucket repositories. When a commit is pushed or a pull request is updated, a build is triggered. However, its status is not reported back to the repository.`cloud-build-status` provides a Google Cloud Function to perform this step. When enabled, you'll see a status icon next to your commits and pull requests.

If you would like a Cloud Build *badge* as well (as seen above) see my [other project](https://github.com/leg100/cloud-build-badge).

Note: There is now a Github app for Cloud Build, that *does* report a build's status. However, it doesn't mirror the Github repository to a Google Cloud Source Repository, and instead retrieves a tarball of the commit to build. There are good reasons to prefer a mirror - Cloud Build events will contain information on the repository (whereas the Github app omits some information, such as the owner of the repository). It's also been found that certain changes to the repository - say, changing the name of the repository - are not picked up by the Github app, and it can take quite a bit of work to remove and re-add the app to reflect the changes. In short, it can be preferable to have fine-grained control of the components that make up your CI/CD pipeline.

## Design

* Permissions assigned according to principle of least privilege
* Lazily load and reuse computationally expensive code paths
* Keep credentials encrypted, and decrypt only on first use
* Unit and integration tests

I got a lot of help from reading Seth Vargo's [Secrets in Serverless blog post](https://www.sethvargo.com/secrets-in-serverless). In choosing to both encrypt the credentials with KMS and store the resulting ciphertext on cloud storage (and having the function retrieve and decrypt them at run-time), the credentials can be rotated at any time without having to re-deploy the function.

## Installation

These instructions apply to both Github and Bitbucket. It's recommended that you set the following environment variables first:

* `GOOGLE_CLOUD_PROJECT`: the project in which cloud resources are created, e.g. `my-uniquely-named-project`
* `CREDENTIALS_BUCKET`: the GCS bucket in which to store encrypted credentials, e.g. `my-uniquely-named-credentials-bucket`
* `BUILD_STATUS_KEYRING`: the name of the KMS keyring, e.g. `production`
* `BUILD_STATUS_KEY`: the name of the KMS key, e.g. `cloud-build-status`

### Setup Cloud Build

Follow these [instructions](https://cloud.google.com/cloud-build/docs/running-builds/automate-builds). Once you've done so, you'll have:

  * A Github or Bitbucket repository mirrored to Cloud Source Repositories
  * A Cloud Build config file (e.g. `cloudbuild.yaml`) in the repository
  * A Cloud Build trigger to run a build when a commit is pushed

Make a note of the Google Cloud project you decide to use. From hereon in, all resources are configured in the context of this project.


### Enable Google Cloud APIs

If you have not previously used Cloud Functions, Cloud KMS, or Cloud Storage, enable the APIs on your Google Cloud Project:

```bash
gcloud services enable \
  cloudfunctions.googleapis.com \
  cloudkms.googleapis.com \
  storage-component.googleapis.com
```

### Create KMS keys

Create KMS keyring and key:

```bash
gcloud kms keyrings create ${BUILD_STATUS_KEYRING} --location global

gcloud kms keys create ${BUILD_STATUS_KEY} \
  --location global \
  --keyring ${BUILD_STATUS_KEYRING} \
  --purpose encryption
```

### Create Storage Bucket

Create Google Cloud Storage bucket in which to store encrypted credentials (the ciphertext):

```bash
gsutil mb gs://${CREDENTIALS_BUCKET}/
```

Next, change the default bucket permissions. By default, anyone with access to the project has access to the data in the bucket. You must do this before storing any data in the bucket!

```bash
gsutil defacl set private gs://${CREDENTIALS_BUCKET}/
```

### Setup Credentials

The function needs credentials with which to authenticate with the Github or Bitbucket API. The credentials need not be the same as that used for mirroring.

Note: this step can be repeated whenever you want to rotate the credentials. There is a make task to perform the rotation: `make rotate`.

#### Github

Nominate a Github user account for this purpose. Create a [personal access token](https://github.com/settings/tokens). Assign it the `repo:status` scope.

Encrypt the username and token and upload the resulting ciphertext to the bucket:

```bash
echo '{"username": "username", "password": "********"}' | \
  gcloud kms encrypt \
  --location global \
  --keyring=${BUILD_STATUS_KEYRING} \
  --key=${BUILD_STATUS_KEY} \
  --ciphertext-file=- \
  --plaintext-file=- | \
  gsutil cp - gs://${CREDENTIALS_BUCKET}/github
```

#### Bitbucket

Nominate a Bitbucket user account for this purpose.  Create an [app password](https://confluence.atlassian.com/bitbucket/app-passwords-828781300.html). Assign it the `repository:read` scope.

Encrypt the username and app password and upload the resulting ciphertext to the bucket:

```bash
echo '{"username": "username", "password": "********"}' | \
  gcloud kms encrypt \
  --location global \
  --keyring=${BUILD_STATUS_KEYRING} \
  --key=${BUILD_STATUS_KEY} \
  --ciphertext-file=- \
  --plaintext-file=- | \
  gsutil cp - gs://${CREDENTIALS_BUCKET}/bitbucket
```

### Configure IAM

Create a new service account for use by the Cloud Function:

```bash
gcloud iam service-accounts create cloud-build-status
```

Grant permissions to read from the bucket:

```bash
gsutil iam ch serviceAccount:cloud-build-status@${GOOGLE_CLOUD_PROJECT}.iam.gserviceaccount.com:legacyBucketReader,legacyObjectReader gs://${CREDENTIALS_BUCKET}
```

Grant minimal permissions to decrypt data using the KMS key created above:

```bash
gcloud kms keys add-iam-policy-binding ${BUILD_STATUS_KEY} \
    --location global \
    --keyring ${BUILD_STATUS_KEYRING} \
    --member "serviceAccount:cloud-build-status@${GOOGLE_CLOUD_PROJECT}.iam.gserviceaccount.com" \
    --role roles/cloudkms.cryptoKeyDecrypter
```

The function now has the permissions to both read the ciphertext from the bucket as well as to decrypt the ciphertext.

## Deploy

Deploy the function:

```bash
gcloud functions deploy cloud-build-status \
    --source . \
    --runtime python37 \
    --entry-point build_status \
    --service-account cloud-build-status@${GOOGLE_CLOUD_PROJECT}.iam.gserviceaccount.com \
    --set-env-vars KMS_CRYPTO_KEY_ID=projects/${GOOGLE_CLOUD_PROJECT}/locations/global/keyRings/${BUILD_STATUS_KEYRING}/cryptoKeys/${BUILD_STATUS_KEY},CREDENTIALS_BUCKET=${CREDENTIALS_BUCKET} \
    --trigger-topic=cloud-builds
```

## Test

There are `make` tasks for running integration tests against a deployed function:

```bash
make integration # run both github and bitbucket tests
make integration-github # run only github tests
make integration-bitbucket # run only bitbucket tests
```

Ensure the following environment variables are set first, according to whether you're running tests against Github, Bitbucket, or both:

* `BB_REPO`: the name of an existing Bitbucket repository
* `BB_REPO_OWNER`: the owner of an existing Bitbucket repository
* `BB_COMMIT_SHA`: an existing commit against which to set and test build statuses
* `BB_USERNAME`: Bitbucket username for API authentication
* `BB_PASSWORD`: Bitbucket (app) password for API authentication
* `GITHUB_REPO`: the name of an existing Bitbucket repository
* `GITHUB_REPO_OWNER`: the owner of an existing Bitbucket repository
* `GITHUB_COMMIT_SHA`: an existing commit against which to set and test build statuses
* `GITHUB_USERNAME`: Github username for API authentication
* `GITHUB_PASSWORD`: Github token for API authentication
