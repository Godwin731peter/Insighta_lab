from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsAdmin(BasePermission):
    """Only admin role."""
    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == 'admin'
        )


class IsAnalyst(BasePermission):
    """
    Read (GET/HEAD/OPTIONS): admin + analyst
    Write (POST/PUT/DELETE): admin only
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return request.user.role in ('admin', 'analyst')
        return request.user.role == 'admin'