# Organization commands

`bootstrap_data_plane` creates the single local Organization and an initial active user in an empty ERP Data Plane database.

Required arguments:

- `--organization-name`
- `--organization-slug`
- `--login`

Optional:

- `--email`

The initial password is read from `IVADOO_BOOTSTRAP_PASSWORD` when set, otherwise it is requested interactively. Passwords are deliberately not accepted as command-line arguments to avoid exposing them in shell history or process listings.

Role assignment and scoped administrative permissions are completed later by the RBAC issue.
