# Contributing to BY Maps

This repository is public so that its research can be checked and reproduced.
Please keep that purpose separate from local development material.

## Before opening a pull request

1. Keep only public research data, public-source snapshots, code, methods,
   and reproducible artifacts in the change.
2. Do not commit credentials, tokens, cookies, private URLs, local `.env`
   files, private correspondence, logs, scratchpads, machine-specific paths,
   or unapproved personal data.
3. Install the local secret check once with `pre-commit install` and run
   `./tools/security-scan.sh` before submitting material that changes source
   files, archives, or history-sensitive content.
4. If a scanner reports a possible secret, do not paste its value into the
   pull request. Classify it locally and use the process in `SECURITY.md` if
   it may be live.

## Public author information

Author names, contacts, and social links may be published only when the
author has explicitly approved that presentation. Treat every other email,
phone number, account identifier, and local username as non-public until
that approval is recorded.

## File classification

The detailed classification and review rules are in
[`docs/security/PUBLICATION_POLICY.md`](docs/security/PUBLICATION_POLICY.md).
