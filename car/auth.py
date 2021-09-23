from base64 import b64encode, b64decode
from time import time
from hashlib import sha224
from functools import wraps

from flask import request, _request_ctx_stack
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


def create_jwt_token(client_id, jwt_secret):
    expire = int(time()) + TOKEN_EXPIRE
    token = jwt.encode({'client_id': client_id, 'exp': expire}, jwt_secret, algorithm='HS256')
    return token, expire


def requires_auth(jwt_secret, requires_admin=False):
    def _requires_auth(f):
        @wraps(f)
        def _func(*args, **kwargs):
            auth_data = request.headers.get("Authorization")
            if not auth_data:
                return {"error": "Authorization header missing"}, 401
            if not auth_data.lower().startswith("bearer"):
                return {"error": "only bearer auth supported"}, 401
            auth_data = auth_data[len("bearer"):].strip()

            try:
                jwt_claims = jwt.decode(auth_data, jwt_secret, algorithms=['HS256'])
            except JWTError as e:
                return {"error": "bad token", "details": str(e)}, 401

            if requires_admin and not jwt_claims.get("is_admin"):
                return {"error": "you must be admin"}, 401

            _request_ctx_stack.top.jwt_claims = jwt_claims
            return f(*args, **kwargs)
        return _func
    return _requires_auth
