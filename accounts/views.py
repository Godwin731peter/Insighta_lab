from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from .services.github import exchange_code_for_token, get_github_user
from .models import User
import requests
from django.conf import settings

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

        response = requests.post(
        "https://github.com/login/oauth/access_token",
        headers={"Accept": "application/json"},
        data={
        "client_id": settings.GITHUB_CLIENT_ID,
        "client_secret": settings.GITHUB_CLIENT_SECRET,
        "code": code,
        "code_verifier": code_verifier,
        "redirect_uri": "http://127.0.0.1:8000/api/v1/auth/github/callback/"
      },
 )

        token_data = exchange_code_for_token(code, code_verifier)

        if "access_token" not in token_data:
           return Response({
          "error": "GitHub token exchange failed",
          "github_response": token_data
           }, status=400)

        github_user = get_github_user(token_data["access_token"])

        print("GITHUB TOKEN RESPONSE:", token_data)

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


class GitHubCallbackView(APIView):
    def get(self, request):
        code = request.GET.get("code")

        if not code:
            return Response({"error": "No code provided"}, status=400)

        token_response = requests.post(
            "https://github.com/login/oauth/access_token",
            json={
                "client_id": settings.GITHUB_CLIENT_ID,
                "client_secret": settings.GITHUB_CLIENT_SECRET,
                "code": code,
                "redirect_uri": "http://127.0.0.1:8000/api/v1/auth/github/callback/"
            },
            headers={"Accept": "application/json"},
        )

        token_json = token_response.json()

        if "access_token" not in token_json:
            return Response({
                "error": "GitHub token exchange failed",
                "github_response": token_json
            }, status=400)

        access_token = token_json["access_token"]

        user_response = requests.get(
            "https://api.github.com/user",
            headers={
                "Authorization": f"Bearer {access_token}"
            },
        )

        return Response(user_response.json())