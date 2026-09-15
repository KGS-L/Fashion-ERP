# ADR-0001 — Separate Control Plane and Data Plane

Status: `accepted`

## Context
Ivadoo must manage platform concerns without centralizing customer business data by default.

## Decision
Separate the platform into a Control Plane and customer ERP Data Plane environments. The Control Plane manages organizations, licenses, subscriptions, modules, installations, versions and support. Customer operational data remains in the Data Plane.

## Consequences
- platform administration is separated from business operations;
- sensitive customer business data is not copied to the Control Plane by default;
- interfaces between both planes must remain minimal and explicit.

## Alternatives
A single centralized application/data plane was rejected because it conflicts with the specification's isolation and deployment model.
