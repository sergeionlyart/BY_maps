# Security policy

BY Maps is a public research repository. Reproducible data, methods, and
public-source snapshots are intentionally published; credentials, private
working material, and personal data that is not explicitly approved are not.

## Reporting a suspected disclosure

Do not open a public issue, pull request, or discussion with a suspected
secret or its full value. Use GitHub's **Report a vulnerability** flow for
this repository and provide only the minimum redacted evidence needed to
identify the location. Maintainers should acknowledge the report, rotate a
live credential before removal, and assess Git history, releases, Actions,
and deployed assets.

Private vulnerability reporting must be enabled in the repository's GitHub
settings; adding this policy file does not enable that setting by itself.

If private vulnerability reporting is unavailable, open a public issue only
to request a private contact channel; do not include the secret, token, or
personal data in that issue.

## Supported reporting scope

Report exposed credentials, access-control bypasses, unintentional personal
data, private files, local environment information, and material that should
not be public. Include a repository path, commit SHA, and a redacted
description rather than a copied credential.
