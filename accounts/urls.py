from django.urls import path
from .views import (
    LoginView,
    RefreshView,
    BrowserLogoutView,
    MeView,
    UserListView,
    GitHubPKCEInitView,
    GitHubBrowserAuthView,
    GitHubCLIAuthView,
    GitHubCallbackView,
)

urlpatterns = [
    # Standard JWT
    path('login/', LoginView.as_view()),
    path('refresh/', RefreshView.as_view()),
    path('logout/', BrowserLogoutView.as_view()),

    # Current user
    path('me/', MeView.as_view()),

    # User management (admin only)
    path('users/', UserListView.as_view()),

    # GitHub OAuth + PKCE
    path('github/pkce/init/', GitHubPKCEInitView.as_view()),
    path('github/browser/', GitHubBrowserAuthView.as_view()),
    path('github/cli/', GitHubCLIAuthView.as_view()),
    path('github/callback/', GitHubCallbackView.as_view()),
]