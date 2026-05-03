import base64
import hashlib
import os
import webbrowser
import requests

CLIENT_ID = "Ov23liw6frrSM43F9FqE"
BACKEND_URL = "http://127.0.0.1:8000/api/v1/auth/github/"


def generate_pkce():
    code_verifier = base64.urlsafe_b64encode(os.urandom(40)).decode().rstrip("=")

    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).decode().rstrip("=")

    return code_verifier, code_challenge


# Step 1: Generate PKCE
code_verifier, code_challenge = generate_pkce()

print("\nCODE VERIFIER (keep this safe):")
print(code_verifier)

# Step 2: Open GitHub Login
auth_url = f"https://github.com/login/oauth/authorize?client_id={CLIENT_ID}&code_challenge={code_challenge}&code_challenge_method=S256"

print("\nOpening GitHub login...")
webbrowser.open(auth_url)

# Step 3: Get code from user
code = input("\nPaste the 'code' from the URL here: ").strip()

# Step 4: Send to backend
response = requests.post(
    BACKEND_URL,
    json={
        "code": code,
        "code_verifier": code_verifier
    }
)

print("\nSTATUS:", response.status_code)

try:
    print("RESPONSE:", response.json())
except Exception:
    print("RAW RESPONSE:", response.text)