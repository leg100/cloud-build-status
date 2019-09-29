set_status() {
  cat tests/event_data.json | \
    jq -r \
    --arg status $1 \
    --arg repo_name "bitbucket_${BB_REPO_OWNER}_${BB_REPO}" \
    --arg commit $BB_COMMIT_SHA \
    '.status = $status | .sourceProvenance.resolvedRepoSource.repoName = $repo_name | .sourceProvenance.resolvedRepoSource.commitSha = $commit | @base64 | {"data": . }'
}

check_status() {
  curl -sS https://${BB_USERNAME}:${BB_PASSWORD}@api.bitbucket.org/2.0/repositories/${BB_REPO_OWNER}/${BB_REPO}/commit/${BB_COMMIT_SHA}/statuses | \
    jq -e --arg status $1 '.values[0].state == $status'
}

@test "in progress" {
  run gcloud functions call bitbucket-build-status --data "$(set_status 'WORKING')"
  [ "$status" -eq 0 ]

  run check_status "INPROGRESS"
  [ "$status" -eq 0 ]
}

@test "success" {
  run gcloud functions call bitbucket-build-status --data "$(set_status 'SUCCESS')"
  [ "$status" -eq 0 ]

  run check_status "SUCCESSFUL"
  [ "$status" -eq 0 ]
}

@test "failure" {
  run gcloud functions call bitbucket-build-status --data "$(set_status 'FAILURE')"
  [ "$status" -eq 0 ]

  run check_status "FAILED"
  [ "$status" -eq 0 ]
}
