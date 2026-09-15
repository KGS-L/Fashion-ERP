from drf_spectacular.extensions import OpenApiAuthenticationExtension


class OpaqueBearerAuthenticationScheme(OpenApiAuthenticationExtension):
    target_class = "ivadoo.identity.authentication.OpaqueBearerAuthentication"
    name = "bearerAuth"

    def get_security_definition(self, auto_schema):
        return {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "Opaque",
        }
