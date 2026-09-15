from ivadoo.extensibility.defaults import BASE_PROTECTED
from ivadoo.extensibility.registry import (
    ModelManifest,
    ModuleManifest,
    register_model,
    register_module,
)


register_module(
    ModuleManifest(
        code="enterprise.crm",
        name="CRM",
        version="1.0.0",
        dependencies=("foundation", "fashion.customers"),
        default_enabled=True,
        edition="business",
        api_prefixes=("/api/v1/crm/",),
    )
)

register_model(
    ModelManifest(
        key="crm.crmsource",
        label="CRM source",
        django_model="crm.CRMSource",
        module_code="enterprise.crm",
        view_permission="enterprise.crm.view",
        manage_permission="enterprise.crm.manage",
        protected_fields=BASE_PROTECTED,
    )
)
register_model(
    ModelManifest(
        key="crm.crmpipelinestage",
        label="CRM pipeline stage",
        django_model="crm.CRMPipelineStage",
        module_code="enterprise.crm",
        view_permission="enterprise.crm.view",
        manage_permission="enterprise.crm.manage",
        protected_fields=BASE_PROTECTED | {"stage_type"},
    )
)
register_model(
    ModelManifest(
        key="crm.crmlead",
        label="CRM lead",
        django_model="crm.CRMLead",
        module_code="enterprise.crm",
        view_permission="enterprise.crm.view",
        manage_permission="enterprise.crm.manage",
        protected_fields=BASE_PROTECTED
        | {
            "status",
            "converted_customer",
            "converted_customer_id",
            "converted_at",
            "converted_by",
            "converted_by_id",
        },
        actions=("convert",),
    )
)
register_model(
    ModelManifest(
        key="crm.crmopportunity",
        label="CRM opportunity",
        django_model="crm.CRMOpportunity",
        module_code="enterprise.crm",
        view_permission="enterprise.crm.view",
        manage_permission="enterprise.crm.manage",
        protected_fields=BASE_PROTECTED
        | {
            "customer",
            "customer_id",
            "converted_at",
            "converted_by",
            "converted_by_id",
        },
        actions=("convert",),
    )
)
register_model(
    ModelManifest(
        key="crm.crmconversionevent",
        label="CRM conversion event",
        django_model="crm.CRMConversionEvent",
        module_code="enterprise.crm",
        view_permission="enterprise.crm.view",
        manage_permission="enterprise.crm.convert",
        protected_fields=BASE_PROTECTED
        | {
            "source_kind",
            "lead",
            "lead_id",
            "opportunity",
            "opportunity_id",
            "customer",
            "customer_id",
            "created_customer",
            "source_snapshot",
            "actor",
            "actor_id",
            "occurred_at",
        },
    )
)
