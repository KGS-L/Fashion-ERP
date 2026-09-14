# Phase branching strategy

FashionERP development is organized by roadmap phase.

Each implementation phase is developed on its own long-lived phase branch and merged into `main` through a pull request once the phase acceptance criteria are satisfied.

Planned phase branches:

- `phase/0-framing`
- `phase/1-foundation`
- `phase/2-fashion-domain`
- `phase/3-operations`
- `phase/4-business`
- `phase/5-enterprise-plus`
- `phase/6-deployment`

Phase branches are created progressively. A new phase branch should normally start from the updated `main` branch after the previous phase has been reviewed and merged, rather than creating all phase branches in advance.

Feature or fix branches may be created from the active phase branch when work needs to be isolated further. They should merge back into the active phase branch before the phase pull request to `main`.

GitHub Actions in this repository are limited to validation and automated tests. Deployment and release automation are intentionally excluded from the current CI workflow.
