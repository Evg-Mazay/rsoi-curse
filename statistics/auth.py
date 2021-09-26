from base64 import b64encode, b64decode
from functools import wraps
from urllib.parse import urlparse
from time import time
from hashlib import sha224
from functools import wraps
from requests import request

from flask import request as flask_request, _request_ctx_stack
from jose import jwt
from jose.exceptions import JWTError

TOKEN_EXPIRE = 60 * 60 * 1  # 1 hour

KNOWN_CLIENTS = {
    "gateway_service": "gateway_12345",
    "car_service": "car_12345",
    "office_service": "office_12345",
    "booking_service": "booking_12345",
    "payment_service": "payment_12345",
    "statistics_service": "statistics_12345"
}

current_token = {}


def create_jwt_token(client_id, jwt_secret):
    expire = int(time()) + TOKEN_EXPIRE
    token = jwt.encode({'client_id': client_id, 'exp': expire}, jwt_secret, algorithm='HS256')
    return token, expire


def requires_auth(jwt_secret):
    def _requires_auth(f):
        @wraps(f)
        def _func(*args, **kwargs):
            auth_data = flask_request.headers.get("Authorization")
            if not auth_data:
                return {"error": "Authorization header missing"}, 401
            if not auth_data.lower().startswith("bearer"):
                return {"error": "only bearer auth supported"}, 401
            auth_data = auth_data[len("bearer"):].strip()

            try:
                jwt_claims = jwt.decode(auth_data, jwt_secret, algorithms=['HS256'])
            except JWTError as e:
                return {"error": "bad token", "details": str(e)}, 401

            _request_ctx_stack.top.jwt_claims = jwt_claims
            return f(*args, **kwargs)
        return _func
    return _requires_auth


def check_for_admin(f):
    @wraps(f)
    def _inner(*args, **kwargs):
        is_service = int(flask_request.headers.get("is_service", 0))
        is_admin = int(flask_request.headers.get("is_admin", 0))
        if not is_admin and not is_service:
            return {"error": "You need to be admin"}, 401
        return f(*args, **kwargs)
    return _inner


def check_for_service(f):
    @wraps(f)
    def _inner(*args, **kwargs):
        is_service = int(flask_request.headers.get("is_service", 0))
        if not is_service:
            return {"error": "This method is for inter-service communication only"}, 401
        return f(*args, **kwargs)
    return _inner


def authorized_request(client_id, client_secret, *args, **kwargs):
    global current_token

    domain = urlparse(args[1]).netloc

    kwargs["headers"] = {
        **kwargs.get('headers', {}),
        "Authorization": f"Bearer {current_token.get(domain)}",
        "is_service": "1",
    }

    result = request(*args, **kwargs)
    if result.status_code != 401:
        return result

    print("re-auth in domain", domain)
    credentials = {"client_id": client_id, "client_secret": client_secret}
    token_response = request("POST", f"http://{domain}/token", json=credentials)
    current_token[domain] = token_response.json()["token"]

    kwargs["headers"]["Authorization"] = f"Bearer {current_token.get(domain)}"
    return request(*args, **kwargs)
