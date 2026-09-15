# Extensibility platform

This Django app owns the cross-cutting extensibility contracts that must remain shared by every FashionERP business module.

The first foundation is the Module Registry:

- code manifests declare module code, version, dependencies, edition and API prefixes;
- `ModuleInstallation` stores organization-local activation state;
- code packages and Django migrations remain deployment/version concerns rather than user-authored runtime migrations;
- disabling a module preserves its business data;
- required modules cannot be disabled;
- dependencies are checked before enabling/disabling;
- Bearer-authenticated API requests are gated server-side so a disabled module is not merely hidden in the UI.

Future pieces in this app add metadata/custom fields, generic data import/export and customization security. See tracker #139.
