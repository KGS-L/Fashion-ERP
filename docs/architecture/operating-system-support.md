# Desktop operating system support

Status: `proposal` — Phase 0 decision required.

The FashionERP specification requires the minimum supported Windows, macOS and Linux versions to be confirmed before implementation.

## Proposed support policy

Rather than targeting the oldest operating systems technically supported by Tauri, FashionERP should define a product support baseline based on currently maintained operating systems.

Proposed minimums:

- **Windows:** Windows 11, on a Microsoft-supported release.
- **macOS:** macOS 14 Sonoma or later.
- **Linux:** Ubuntu 24.04 LTS or later as the initially supported reference distribution. Other compatible Linux distributions may be evaluated separately rather than guaranteed from the first release.

## Compatibility note

Tauri itself supports older operating systems than this proposal. The FashionERP product baseline can intentionally be stricter to reduce security, packaging, WebView and support complexity.

## Windows 10

Windows 10 reached general end of support in October 2025. It may still be technically capable of running a Tauri application, but it should not be treated as the normal FashionERP production baseline unless a specific pilot requires a temporary compatibility policy.

## Decision required

Before this document can move to `accepted`, confirm whether the proposed minimums are retained or adjusted.
