# ADR 0012 — Python 3.14 and Django 5.2 LTS runtime baseline

Status: `accepted`

Decision owner: Phase 1 / issue #33.

## Context

FashionERP has validated Django as its backend framework and Django REST Framework + drf-spectacular + django-filter as its REST/OpenAPI stack.

The FashionERP specification does not prescribe a Python or Django version. The runtime therefore requires an explicit project decision based on current upstream support, compatibility and the long-lived nature of an ERP product.

Research performed for issue #33 on 2026-09-14 shows:

- Django 5.2 is the current Django LTS line and receives security updates for at least three years from its April 2025 release;
- Django 5.2 supports Python 3.14 from Django 5.2.8 onward;
- Django 6.1 is current but is not an LTS release;
- Django REST Framework supports Django 5.2 and Python 3.14;
- drf-spectacular 0.30.0 explicitly supports Django 5.2, Python 3.14 and DRF through the 3.17 series;
- django-filter 25.2 supports Django 5.2, while later releases also test Python 3.14.

## Decision

Use **Python 3.14** as the FashionERP server runtime series and **Django 5.2 LTS** as the Django framework series for the initial implementation baseline.

Dependency compatibility baseline for initial scaffolding:

- Python: `>=3.14,<3.15`;
- Django: `>=5.2.8,<5.3`, always using the latest available 5.2.x security/bugfix patch;
- Django REST Framework: use the latest compatible **3.17.x** patch while drf-spectacular 0.30.0 officially lists support through DRF 3.17;
- drf-spectacular: `0.30.x` initially, pinned because its maintainers explicitly recommend pinning and reviewing schema diffs on upgrade;
- django-filter: a release line officially compatible with Django 5.2 and the selected DRF version.

Exact transitive dependency locking belongs to the server scaffold/dependency-management implementation and must be reproducible.

## Why Django 5.2 LTS instead of Django 6.1

Django 6.1 is newer and supports Python 3.12–3.14, but its mainstream/extended support window is shorter than the 5.2 LTS line.

More importantly for the already validated FashionERP API stack, drf-spectacular 0.30.0 currently documents Django support through 6.0 and DRF through 3.17, while DRF 3.18 is the release adding Django 6.1 support. Choosing Django 6.1 now would therefore move FashionERP ahead of the officially documented compatibility matrix of the selected OpenAPI generator.

For an ERP foundation, the LTS line with a fully aligned dependency matrix is preferred over adopting the newest non-LTS Django release.

## Why Python 3.14

Python 3.14 is the current stable feature series and is officially supported by Django 5.2, current DRF and the selected drf-spectacular line.

Starting a new codebase on 3.14 avoids selecting a runtime series already closer to its bugfix-support transition while retaining a supported and tested dependency combination.

FashionERP uses the normal CPython build. Experimental free-threaded/no-GIL builds are not part of this baseline.

## Update policy

- pin the Python minor series and use current 3.14.x patch releases;
- pin Django to the 5.2 LTS series and apply supported 5.2.x security/bugfix updates promptly;
- pin drf-spectacular and inspect generated OpenAPI schema diffs before upgrades;
- upgrade DRF/django-filter only inside the compatibility matrix validated by CI;
- run unit, integration, authorization/isolation, migration and OpenAPI validation tests after dependency updates;
- do not move to Django 6.x/7.x merely because a newer feature release exists;
- evaluate the next Django LTS as a planned migration with explicit compatibility testing and an ADR update.

## Consequences

- the initial Django scaffold can be generated against a stable runtime target;
- the REST/OpenAPI stack has an upstream-supported compatibility intersection;
- security patches can be adopted without changing the chosen major/minor framework baseline;
- CI and local development must use the same Python/Django series;
- Docker images and deployment manifests must not silently use a different Python minor series.

## Alternatives considered

### Python 3.13 + Django 5.2 LTS

Technically compatible and conservative, but Python 3.14 is already stable and supported by the selected stack. Starting a new project on 3.14 provides the longer forward runtime horizon.

### Python 3.14 + Django 6.1

Rejected for the initial baseline because Django 6.1 is non-LTS and the selected drf-spectacular release does not yet document Django 6.1 / DRF 3.18 in its supported matrix.

## Validation

Explicitly validated by the FashionERP project owner in issue #33 on 2026-09-14.
