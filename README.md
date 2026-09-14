# FashionERP

FashionERP is a modular ERP platform built for fashion, textile and garment businesses.

It is designed for fashion houses, tailoring workshops, ready-to-wear brands, uniform manufacturers, textile companies, fabric distributors and multi-site fashion groups.

The main FashionERP modules include:

- CRM and customer management
- Measurements and made-to-measure workflows
- Products, materials and variants
- Collections, designs and PLM
- Sales and orders
- Inventory and warehouses
- Purchasing and suppliers
- Manufacturing and MRP
- Quality control
- Employees and teams
- Subcontracting
- Delivery and returns
- Expenses, finance and accounting
- Reporting and business intelligence

FashionERP modules are designed to work together as one integrated system, from customer acquisition and product design to production, delivery and profitability analysis.

The platform is built around a modular, multi-company and multi-establishment architecture, with support planned for managed cloud, private server and on-premise deployments.

## Project status

FashionERP is currently in active development.

Phase 1 Foundation is implemented on the `phase/1-foundation` branch and is being prepared for final review. It includes authentication/session security, organizations, companies, establishments, scoped RBAC, immutable audit, internationalization, versioned REST/OpenAPI contracts, PostgreSQL migrations and Foundation integration tests.

Business modules such as CRM, products, orders, inventory, purchasing and manufacturing remain future phases and are not presented as implemented Foundation capabilities.

## Documentation

Project documentation and module specifications are maintained in the `docs/` directory. The implemented Foundation behavior is summarized in `docs/foundation/README.md`.

## Security

Security is a core requirement of FashionERP. The platform is designed around strict organization isolation, role-based access control, auditability and protection of sensitive business data.

Security reporting procedures will be documented before the first public release.

## License

FashionERP follows an open-core direction. Unless a source file or directory states otherwise, the Community core is licensed under LGPL-3.0-only as described in the repository `LICENSE` file. Future commercial components remain separately licensed.
