from django.test import SimpleTestCase
from django.urls import Resolver404, resolve
from drf_spectacular.generators import SchemaGenerator
from rest_framework import status
from rest_framework.test import APIClient

from .pagination import StandardPageNumberPagination


FOUNDATION_OPENAPI_PATHS = {
    "/api/v1/auth/login/",
    "/api/v1/auth/logout/",
    "/api/v1/auth/me/",
    "/api/v1/auth/sessions/",
    "/api/v1/auth/sessions/revoke-others/",
    "/api/v1/auth/sessions/{session_id}/revoke/",
    "/api/v1/auth/2fa/",
    "/api/v1/auth/2fa/totp/setup/",
    "/api/v1/auth/2fa/totp/confirm/",
    "/api/v1/auth/2fa/disable/",
    "/api/v1/auth/2fa/recovery-codes/regenerate/",
    "/api/v1/organizations/",
    "/api/v1/organizations/{organization_id}/",
    "/api/v1/companies/",
    "/api/v1/companies/{company_id}/",
    "/api/v1/establishments/",
    "/api/v1/establishments/{establishment_id}/",
    "/api/v1/access/permissions/",
    "/api/v1/access/roles/",
    "/api/v1/access/roles/{role_id}/",
    "/api/v1/access/groups/",
    "/api/v1/access/groups/{group_id}/",
    "/api/v1/access/grants/",
    "/api/v1/access/grants/{grant_id}/revoke/",
    "/api/v1/access/users/",
    "/api/v1/access/users/{user_id}/",
    "/api/v1/access/users/{user_id}/2fa/reset/",
    "/api/v1/audit/events/",
    "/api/v1/i18n/languages/",
    "/api/v1/i18n/catalog/",
    "/api/v1/i18n/context/",
    "/api/v1/i18n/currencies/",
    "/api/v1/i18n/currencies/{currency_code}/",
    "/api/v1/i18n/exchange-rates/",
    "/api/v1/i18n/exchange-rates/{rate_id}/",
    "/api/v1/i18n/units/",
    "/api/v1/i18n/units/{unit_id}/",
}

DEFERRED_BUSINESS_PREFIXES = (
    "/api/v1/inventory/",
    "/api/v1/purchases/",
    "/api/v1/manufacturing/",
    "/api/v1/deliveries/",
    "/api/v1/reports/",
)

ENTERPRISE_PLUS_FRAGMENTS = (
    "/api-keys/",
    "/api_keys/",
    "/webhooks/",
)


class FoundationOpenApiContractTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.schema = SchemaGenerator().get_schema(request=None, public=True)
        cls.paths = cls.schema["paths"]

    def test_all_implemented_foundation_routes_are_in_openapi(self):
        missing = FOUNDATION_OPENAPI_PATHS.difference(self.paths)
        self.assertEqual(
            missing,
            set(),
            msg=f"Foundation routes missing from OpenAPI: {sorted(missing)}",
        )

    def test_deferred_business_routes_are_not_exposed(self):
        exposed = [
            path
            for path in self.paths
            if path.startswith(DEFERRED_BUSINESS_PREFIXES)
        ]
        self.assertEqual(
            exposed,
            [],
            msg=f"Deferred business routes exposed early: {exposed}",
        )

    def test_enterprise_plus_api_keys_and_webhooks_are_not_exposed(self):
        exposed = [
            path
            for path in self.paths
            if any(fragment in path for fragment in ENTERPRISE_PLUS_FRAGMENTS)
        ]
        self.assertEqual(
            exposed,
            [],
            msg=f"Enterprise Plus routes exposed during Foundation: {exposed}",
        )

    def test_deferred_and_enterprise_plus_paths_are_not_routed(self):
        forbidden_paths = [
            *DEFERRED_BUSINESS_PREFIXES,
            "/api/v1/api-keys/",
            "/api/v1/webhooks/",
        ]
        for path in forbidden_paths:
            with self.subTest(path=path):
                with self.assertRaises(Resolver404):
                    resolve(path)

    def test_openapi_declares_opaque_bearer_authentication(self):
        security_schemes = self.schema["components"]["securitySchemes"]
        bearer = security_schemes["bearerAuth"]

        self.assertEqual(bearer["type"], "http")
        self.assertEqual(bearer["scheme"], "bearer")
        self.assertEqual(bearer["bearerFormat"], "Opaque")

    def test_company_collection_documents_pagination_filter_search_and_ordering(self):
        operation = self.paths["/api/v1/companies/"]["get"]
        parameters = {
            parameter["name"]: parameter
            for parameter in operation.get("parameters", [])
        }

        for expected in (
            "page",
            "page_size",
            "status",
            "country_code",
            "search",
            "ordering",
        ):
            self.assertIn(expected, parameters)

    def test_establishment_collection_documents_declared_filters(self):
        operation = self.paths["/api/v1/establishments/"]["get"]
        parameter_names = {
            parameter["name"]
            for parameter in operation.get("parameters", [])
        }

        for expected in (
            "page",
            "page_size",
            "company_id",
            "status",
            "site_type",
            "country_code",
            "search",
            "ordering",
        ):
            self.assertIn(expected, parameter_names)

    def test_pagination_baseline_is_stable(self):
        self.assertEqual(StandardPageNumberPagination.page_size, 50)
        self.assertEqual(
            StandardPageNumberPagination.page_size_query_param,
            "page_size",
        )
        self.assertEqual(StandardPageNumberPagination.max_page_size, 100)


class FoundationApiEnvelopeTests(SimpleTestCase):
    def setUp(self):
        self.client = APIClient()

    def test_unauthenticated_error_uses_stable_envelope_and_request_id(self):
        response = self.client.get(
            "/api/v1/companies/",
            HTTP_X_REQUEST_ID="contract-test-request",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(
            response.data["error"]["code"],
            "authentication_required",
        )
        self.assertTrue(response.data["error"]["message"])
        self.assertEqual(response.data["error"]["details"], {})
        self.assertEqual(
            response.data["error"]["request_id"],
            "contract-test-request",
        )

    def test_openapi_schema_and_interactive_docs_are_available(self):
        schema_response = self.client.get("/api/schema/")
        docs_response = self.client.get("/api/docs/")

        self.assertEqual(schema_response.status_code, status.HTTP_200_OK)
        self.assertEqual(docs_response.status_code, status.HTTP_200_OK)
