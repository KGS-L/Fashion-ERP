from rest_framework.exceptions import AuthenticationFailed


class TwoFactorRequired(AuthenticationFailed):
    default_detail = "Two-factor authentication code required."
    default_code = "two_factor_required"
    ivadoo_code = "two_factor_required"


class InvalidSecondFactor(AuthenticationFailed):
    default_detail = "Invalid two-factor authentication code."
    default_code = "invalid_two_factor"
    ivadoo_code = "invalid_two_factor"
