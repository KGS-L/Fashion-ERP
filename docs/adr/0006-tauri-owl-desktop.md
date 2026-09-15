# ADR-0006 — Tauri + Owl/TypeScript for the desktop application

Status: `accepted`

## Context
Ivadoo requires an installable PC application for administration, configuration, accounting, production, inventory, purchasing, reporting and multi-company operation.

## Decision
Use Tauri with Owl/TypeScript for the installable desktop application, connected to the Ivadoo API.

## Consequences
- `apps/desktop` follows this stack;
- desktop clients must support the validated cloud/local/private-server modes;
- supported operating-system baseline is Windows 11, macOS 14+ and Ubuntu 24.04 LTS+;
- Windows 10 may be tested for a pilot but is not an officially supported production baseline.

## Alternatives
No alternative desktop framework is part of the current baseline.
