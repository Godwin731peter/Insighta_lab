import requests

GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"

def exchange_code_for_token(code, code_verifier):
    response = requests.post(
        GITHUB_TOKEN_URL,
        headers={"Accept": "application/json"},
        data={
            "client_id": "YOUR_CLIENT_ID",
            "client_secret": "YOUR_CLIENT_SECRET",
            "code": code,
            "code_verifier": code_verifier,
        },
    )
    return response.json()

def get_github_user(access_token):
    response = requests.get(
        GITHUB_USER_URL,
        headers={"Authorization": f"Bearer {access_token}"}
    )
    return response.json()