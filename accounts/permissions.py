from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == "admin"


class IsAnalyst(BasePermission):
    """Analysts and admins can read. Only admins can write."""
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return request.user.role in ("admin", "analyst")
        return request.user.role == "admin"


class IsAuthenticatedWithCookie(BasePermission):
    """
    Allows JWT from Authorization header (CLI) or access_token cookie (browser).
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated