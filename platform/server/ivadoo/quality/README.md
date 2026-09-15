# Quality

Phase 3 quality domain for simple receiving, in-process and final inspections.

It records configurable inspection criteria, defects and photo references, accept/reject/rework decisions, rework completion and reinspection history. Blocking quality decisions can prevent the next operational transition while preserving an auditable history.

The module exposes scoped REST resources under `/api/v1/quality/` and follows organization/company RBAC isolation. Advanced statistical quality, BI and client fitting/alteration workflows remain outside this package at this phase.

The quality capability is registered independently from purchasing and manufacturing at runtime so those modules can still be disabled without destroying historical quality records. Context-specific inspections may reference their records when those domains are present.
