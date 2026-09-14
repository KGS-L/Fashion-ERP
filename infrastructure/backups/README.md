# Backups and restore

FashionERP requires backups for both PostgreSQL databases and the file/object storage layer.

The specification calls for:

- at least daily backups;
- daily, weekly and monthly retention;
- encrypted backups stored separately;
- periodic restoration tests;
- complete export capability for customers.

Implementation scripts and restore procedures will be maintained here.