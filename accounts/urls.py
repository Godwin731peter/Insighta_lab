# accounts/urls.py
from django.urls import path
from .views import LoginView, RefreshView, GitHubAuthView, GitHubCallbackView

urlpatterns = [
    path('login/', LoginView.as_view()),
    path('refresh/', RefreshView.as_view()),
    path('github/', GitHubAuthView.as_view()),
    path('auth/github/callback/', GitHubCallbackView.as_view()),
]