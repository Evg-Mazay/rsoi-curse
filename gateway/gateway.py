from functools import wraps

from requests import request

from jose import jwt, JWTError, ExpiredSignatureError
from flask import Flask
from flask import request as flask_request
from flask_cors import CORS

# Экземпляр приложения
app = Flask(__name__)
cors = CORS(app)
app.config['CORS_HEADERS'] = 'Content-Type'
CLIENT_ID = "gateway_service"
JWT_SECRET = "gateway_12345"
USER_JWT_SECRET = "user_jwt_secret"
current_token = None


CAR_SERVICE_URL = "localhost:7774"
OFFICE_SERVICE_URL = "localhost:7775"
PAYMENT_SERVICE_URL = "localhost:7776"
BOOKING_SERVICE_URL = "localhost:7777"
STATISTICS_SERVICE_URL = "localhost:7778"


ROUTING_TABLE = {
    "cars": CAR_SERVICE_URL,
    "offices": OFFICE_SERVICE_URL,
    "payment": PAYMENT_SERVICE_URL,
    "booking": BOOKING_SERVICE_URL,
    "reports": STATISTICS_SERVICE_URL,
}


def authorized_request(domain, *args, **kwargs):
    global current_token

    kwargs["headers"] = {"Authorization": f"Bearer {current_token}"}
    result = request(*args, **kwargs)
    if result.status_code != 401:
        return result

    credentials = {"client_id": CLIENT_ID, "client_secret": JWT_SECRET}
    token_response = request("POST", f"http://{domain}/token", json=credentials)
    current_token = token_response.json()["token"]

    kwargs["headers"] = {"Authorization": f"Bearer {current_token}"}
    return request(*args, **kwargs)


class RoleError(Exception):
    pass


def requires_auth(requires_admin=False):
    """
    Декоратор, валидирующий jwt-токен
    """
    def _requires_auth(f):
        @wraps(f)
        def inner(*args, **kwargs):
            auth_header = flask_request.headers.get("Authorization")
            if auth_header:
                body = jwt.decode(auth_header, JWT_SECRET, algorithms=['HS256'])
                if requires_admin and not body.get("is_admin"):
                    raise RoleError(f"You must be admin to do this")
            return f(*args, **kwargs)
        return inner
    return _requires_auth


def verify_token_from_cookie():
    auth_header = flask_request.cookies.get("token")
    print("cookies:", auth_header, flask_request.cookies)
    if auth_header:
        body = jwt.decode(auth_header, USER_JWT_SECRET, algorithms=['HS256'])
        return {"requested_by": body}
    return None


@app.after_request
def add_cors(response):
    header = response.headers
    header['Access-Control-Allow-Origin'] = 'http://localhost:7770'
    header['Access-Control-Allow-Headers'] = 'Origin, Content-Type'
    header['Access-Control-Allow-Credentials'] = 'true'
    header['Access-Control-Allow-Methods'] = 'HEAD, GET, POST, DELETE, PUT'
    return response


@app.errorhandler(ExpiredSignatureError)
@app.errorhandler(JWTError)
def error_401(error):
    return str(error), 401


@app.errorhandler(RoleError)
def error_403(error):
    return str(error), 403


@app.route('/')
# @requires_auth(requires_admin=True)
def hello_world():
    return 'Gateway is working'


@app.route('/<path:path>', methods=['GET', 'HEAD', 'POST', 'PUT', 'DELETE', 'PATCH'])
def route(path):
    user = verify_token_from_cookie()
    if not user:
        return {"error": "bad token"}, 401

    for route, service in ROUTING_TABLE.items():
        if path.startswith(route):
            result = authorized_request(
                service,
                flask_request.method,
                f"http://{service}/{path}",
                json=flask_request.json,
            )
            return result.text, result.status_code, result.headers.items()
    return {"error": 'No route from gateway'}, 400


# Точка входа ##############################

if __name__ == '__main__':
    app.run(host="127.0.0.1", port=7779)

