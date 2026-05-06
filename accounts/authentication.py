from rest_framework_simplejwt.authentication import JWTAuthentication


class CookieOrHeaderJWTAuthentication(JWTAuthentication):
    """
    Checks Authorization header first (CLI), then falls back to
    access_token HTTP-only cookie (browser).
    """
    def authenticate(self, request):
        # Try header first (CLI flow)
        header_result = super().authenticate(request)
        if header_result is not None:
            return header_result

        # Fall back to cookie (browser flow)
        raw_token = request.COOKIES.get("access_token")
        if raw_token is None:
            return None

        validated = self.get_validated_token(raw_token)
        user = self.get_user(validated)
        return user, validated