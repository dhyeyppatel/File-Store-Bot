import secrets
import hashlib

def generate_token():
    # URL safe random string (e.g. 16 bytes = ~22 chars)
    return secrets.token_urlsafe(16)

def hash_token(token):
    return hashlib.sha256(token.encode('utf-8')).hexdigest()
