import base64
import hashlib
import secrets
import string

import requests
from django.conf import settings
from django.middleware.csrf import get_token
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from accounts.authentication import CookieOrHeaderJWTAuthentication
from core.permissions import IsAdmin, IsAnalyst
from core.pagination import StandardPagination
from .models import User


# ── PKCE helpers ──────────────────────────────────────────────────────────────

def generate_pkce_pair():
    alphabet = string.ascii_letters + string.digits + '-._~'
    code_verifier = ''.join(secrets.choice(alphabet) for _ in range(64))
    digest = hashlib.sha256(code_verifier.encode()).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b'=').decode()
    return code_verifier, code_challenge


def exchange_github_code(code, code_verifier, redirect_uri):
    resp = requests.post(
        'https://github.com/login/oauth/access_token',
        headers={'Accept': 'application/json'},
        data={
            'client_id': settings.GITHUB_CLIENT_ID,
            'client_secret': settings.GITHUB_CLIENT_SECRET,
            'code': code,
            'code_verifier': code_verifier,
            'redirect_uri': redirect_uri,
        },
    )
    return resp.json()


def fetch_github_user(access_token):
    headers = {'Authorization': f'Bearer {access_token}'}
    user_resp = requests.get('https://api.github.com/user', headers=headers)
    if user_resp.status_code != 200:
        return None, None

    github_user = user_resp.json()
    email = github_user.get('email')

    if not email:
        email_resp = requests.get('https://api.github.com/user/emails', headers=headers)
        if email_resp.status_code == 200:
            primary = next((e for e in email_resp.json() if e.get('primary')), None)
            email = primary['email'] if primary else ''

    return github_user, email


def get_or_create_user(github_user, email):
    return User.objects.get_or_create(
        github_id=github_user['id'],
        defaults={
            'username': github_user['login'],
            'email': email or '',
            'avatar_url': github_user.get('avatar_url', ''),
            'github_login': github_user.get('login', ''),
        },
    )


def issue_jwt(user):
    refresh = RefreshToken.for_user(user)
    return str(refresh.access_token), str(refresh)


# ── Standard JWT ──────────────────────────────────────────────────────────────

class LoginView(TokenObtainPairView):
    pass


class RefreshView(TokenRefreshView):
    pass


# ── PKCE Init — shared by CLI + browser ──────────────────────────────────────

class GitHubPKCEInitView(APIView):
    """
    GET /api/v1/auth/github/pkce/init/
    CLI sends its own state + code_challenge.
    Browser: backend generates both.
    """
    def get(self, request):
        redirect_uri = request.GET.get('redirect_uri', settings.GITHUB_REDIRECT_URI)
        state = request.GET.get('state') or secrets.token_urlsafe(32)
        external_challenge = request.GET.get('code_challenge')

        if external_challenge:
            code_challenge = external_challenge
            code_verifier = None
        else:
            code_verifier, code_challenge = generate_pkce_pair()

        auth_url = (
            f'https://github.com/login/oauth/authorize'
            f'?client_id={settings.GITHUB_CLIENT_ID}'
            f'&code_challenge={code_challenge}'
            f'&code_challenge_method=S256'
            f'&redirect_uri={redirect_uri}'
            f'&state={state}'
            f'&scope=read:user user:email'
        )

        payload = {'authorization_url': auth_url, 'state': state}
        if code_verifier:
            payload['code_verifier'] = code_verifier

        return Response(payload)


# ── Browser OAuth — HTTP-only cookies ────────────────────────────────────────

class GitHubBrowserAuthView(APIView):
    """
    POST /api/v1/auth/github/browser/
    Body: { code, code_verifier, redirect_uri }
    Sets tokens as HTTP-only cookies.
    """
    def post(self, request):
        code = request.data.get('code')
        code_verifier = request.data.get('code_verifier')
        redirect_uri = request.data.get('redirect_uri', settings.GITHUB_REDIRECT_URI)

        if not code or not code_verifier:
            return Response({'error': 'code and code_verifier are required'}, status=400)

        token_data = exchange_github_code(code, code_verifier, redirect_uri)

        if 'access_token' not in token_data:
            return Response({
                'error': 'GitHub token exchange failed',
                'github_response': token_data,
            }, status=400)

        github_user, email = fetch_github_user(token_data['access_token'])
        if not github_user:
            return Response({'error': 'Failed to fetch GitHub user'}, status=400)

        user, _ = get_or_create_user(github_user, email)
        access_token, refresh_token = issue_jwt(user)

        response = Response({'message': 'Login successful', 'role': user.role})

        access_max_age = int(settings.SIMPLE_JWT['ACCESS_TOKEN_LIFETIME'].total_seconds())
        refresh_max_age = int(settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'].total_seconds())

        response.set_cookie(
            'access_token', access_token,
            httponly=True, secure=not settings.DEBUG,
            samesite='Lax', max_age=access_max_age,
        )
        response.set_cookie(
            'refresh_token', refresh_token,
            httponly=True, secure=not settings.DEBUG,
            samesite='Lax', max_age=refresh_max_age,
        )

        get_token(request)  # ensure CSRF cookie is set
        return response


class BrowserLogoutView(APIView):
    authentication_classes = [CookieOrHeaderJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        response = Response({'message': 'Logged out'})
        response.delete_cookie('access_token')
        response.delete_cookie('refresh_token')
        return response


# ── CLI OAuth — returns JSON tokens ──────────────────────────────────────────

class GitHubCLIAuthView(APIView):
    """
    POST /api/v1/auth/github/cli/
    Body: { code, code_verifier, redirect_uri }
    Returns tokens as JSON → stored in ~/.insighta/credentials.json
    """
    def post(self, request):
        code = request.data.get('code')
        code_verifier = request.data.get('code_verifier')
        redirect_uri = request.data.get('redirect_uri')

        if not all([code, code_verifier, redirect_uri]):
            return Response(
                {'error': 'code, code_verifier, and redirect_uri are required'},
                status=400,
            )

        token_data = exchange_github_code(code, code_verifier, redirect_uri)

        if 'access_token' not in token_data:
            return Response({
                'error': 'GitHub token exchange failed',
                'github_response': token_data,
            }, status=400)

        github_user, email = fetch_github_user(token_data['access_token'])
        if not github_user:
            return Response({'error': 'Failed to fetch GitHub user'}, status=400)

        user, _ = get_or_create_user(github_user, email)
        access_token, refresh_token = issue_jwt(user)

        return Response({
            'access_token': access_token,
            'refresh_token': refresh_token,
            'username': user.username,
            'role': user.role,
        })


# ── GitHub callback passthrough ───────────────────────────────────────────────

class GitHubCallbackView(APIView):
    """
    GET /api/v1/auth/github/callback/?code=xxx&state=yyy
    GitHub redirects here. Returns code for frontend/CLI to complete the flow.
    """
    def get(self, request):
        code = request.GET.get('code')
        state = request.GET.get('state', '')
        if not code:
            return Response({'error': 'No code provided'}, status=400)
        return Response({
            'code': code,
            'state': state,
            'message': 'Send this code with your code_verifier to complete login.',
        })


# ── Me ────────────────────────────────────────────────────────────────────────

class MeView(APIView):
    authentication_classes = [CookieOrHeaderJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        u = request.user
        return Response({
            'id': u.id,
            'username': u.username,
            'email': u.email,
            'role': u.role,
            'avatar_url': u.avatar_url,
            'github_login': u.github_login,
        })


# ── User list (admin only) ────────────────────────────────────────────────────

class UserListView(APIView):
    authentication_classes = [CookieOrHeaderJWTAuthentication]
    permission_classes = [IsAdmin]

    def get(self, request):
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 20))
        offset = (page - 1) * page_size

        queryset = User.objects.all().order_by('id')
        total = queryset.count()
        users = queryset[offset: offset + page_size]

        return Response({
            'pagination': {
                'page': page,
                'page_size': page_size,
                'total': total,
                'total_pages': -(-total // page_size),
                'has_next': offset + page_size < total,
                'has_previous': page > 1,
            },
            'results': [
                {
                    'id': u.id,
                    'username': u.username,
                    'email': u.email,
                    'role': u.role,
                    'github_login': u.github_login,
                    'avatar_url': u.avatar_url,
                }
                for u in users
            ],
        })