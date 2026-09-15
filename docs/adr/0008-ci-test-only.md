# ADR-0008 — GitHub Actions CI is test-only

Status: `accepted`

## Context
Ivadoo needs automated validation from the beginning, while deployment/provider choices remain separate and some implementation technologies are still open.

## Decision
Use GitHub Actions for repository validation and automated tests only at this stage. CI may evolve to run linting, unit, integration, security, migration and contract tests as they become available, but it must not deploy production environments, publish releases or provision customer infrastructure.

## Consequences
- failing checks block phase review/fusion;
- workflows may run on `main`, pull requests and `phase/**` branches;
- deployment automation requires a later explicit decision;
- production secrets are not required by the test CI.

## Alternatives
Combining CI and automatic deployment from the beginning was rejected for the current stage.
