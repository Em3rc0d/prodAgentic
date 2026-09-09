# S5 Candidate Freeze Policy

S5 candidate freeze is fail-closed.

A SHA may be called the **S5 frozen candidate** only after all seven independent checks below have completed successfully against that exact SHA:

```text
backend-test
frontend-test
UI-01-CERT browser
DOCKER-COMPOSE-LOCAL smoke
S3-CERT structured-agent-cell
S4-CERT visualspec-v1
S5-CERT renderer-assetstore
```

Before freeze, the final changed-file diff from S4-entry main must be reviewed for authority drift. Any subsequent product, test or workflow commit supersedes the candidate and requires a fresh 7/7 consensus.

After freeze, only certification-receipt/documentation changes are allowed on the receipt head. That head is separately required to pass the same 7/7 consensus before exact-head merge. The merge commit is then required to pass post-merge 7/7 before S5 can be declared `CERTIFIED / MERGED`.
