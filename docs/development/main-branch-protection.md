# `main` branch protection baseline

Status: required repository-administration follow-up from hardening issue #169.

The repository currently has no GitHub ruleset for `main`. The connected automation used during this hardening can read repository rulesets but does not expose an administrative write operation for creating them, so this configuration must be applied in GitHub repository settings.

## Recommended ruleset

Create an active branch ruleset named **Protect main** targeting the default branch `main`.

Enable:

- restrict deletions;
- block force pushes;
- require a pull request before merging;
- required approvals: **0** while the repository has a single maintainer, so the owner is not blocked from merging their own reviewed CI-clean PR;
- require conversation resolution before merging;
- require status checks to pass before merging;
- require the branch to be up to date before merging.

Do **not** require linear history because Ivadoo intentionally uses explicit merge commits for phase gates.

## Required checks

Require the current stable check names produced by the two test-only workflows:

- `Django / Python 3.14`;
- `Verify Ivadoo naming`;
- `High-risk secret pattern scan`;
- `Test .github structure`;
- `Test apps structure`;
- `Test platform structure`;
- `Test modules structure`;
- `Test infrastructure structure`;
- `Test localizations structure`;
- `Test docs structure`;
- `Test tests structure`.

If GitHub displays a check under a slightly different generated context name, select the check emitted by the latest successful `Backend Tests` or `Repository Tests` run rather than inventing a new context.

## Bypass policy

Do not configure a routine bypass for the project owner. If an emergency bypass is ever needed, it must be temporary and followed by a normal PR that restores a green `main` state and documents why the bypass was used.

## CI rule

Branch protection does not change the existing architecture decision: GitHub Actions remains limited to validation and tests. No deployment, provisioning, release or publishing action is authorized by this ruleset.
