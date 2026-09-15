# Infrastructure

Deployment and operational assets for Ivadoo belong here.

The specifications require support for:

- Managed cloud
- Customizable cloud environments
- On-premise installation
- Private server deployment
- Docker-based supported installation for on-premise scenarios
- PostgreSQL
- S3-compatible object storage or MinIO
- Backup and restore procedures
- Monitoring and observability
- Separate development, test, staging and production environments

Current structure:

- `docker/`
- `postgresql/`
- `storage/`
- `backups/`
- `monitoring/`
- `environments/`

Infrastructure implementation will be added progressively as deployment choices are validated.