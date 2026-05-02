from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from .services.github import exchange_code_for_token, get_github_user
from .models import User

# Create your views here.
# accounts/views.py

from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

class LoginView(TokenObtainPairView):
    pass

class RefreshView(TokenRefreshView):
    pass

class GitHubAuthView(APIView):
    def post(self, request):
        code = request.data.get("code")
        code_verifier = request.data.get("code_verifier")

        token_data = exchange_code_for_token(code, code_verifier)
        github_user = get_github_user(token_data["access_token"])

        user, _ = User.objects.get_or_create(
            github_id=github_user["id"],
            defaults={
                "username": github_user["login"],
            }
        )

 # generate JWT manually
        from rest_framework_simplejwt.tokens import RefreshToken
        refresh = RefreshToken.for_user(user)

        return Response({
            "access": str(refresh.access_token),
            "refresh": str(refresh),
        })