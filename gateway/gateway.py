from functools import wraps
import os

from requests import request, RequestException

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
current_token = {}

FRONT_URL = os.environ.get("FRONT_URL", "localhost:7770")
CAR_SERVICE_URL = os.environ.get("CAR_SERVICE_URL", "localhost:7774")
OFFICE_SERVICE_URL = os.environ.get("OFFICE_SERVICE_URL", "localhost:7775")
PAYMENT_SERVICE_URL = os.environ.get("PAYMENT_SERVICE_URL", "localhost:7776")
BOOKING_SERVICE_URL = os.environ.get("BOOKING_SERVICE_URL", "localhost:7777")
STATISTICS_SERVICE_URL = os.environ.get("STATISTICS_SERVICE_URL", "localhost:7778")

print("FRONT_URL:", FRONT_URL)
print("CAR_SERVICE_URL:", CAR_SERVICE_URL)
print("OFFICE_SERVICE_URL:", OFFICE_SERVICE_URL)
print("PAYMENT_SERVICE_URL:", PAYMENT_SERVICE_URL)
print("BOOKING_SERVICE_URL:", BOOKING_SERVICE_URL)
print("STATISTICS_SERVICE_URL:", STATISTICS_SERVICE_URL)

ROUTING_TABLE = {
    "cars": CAR_SERVICE_URL,
    "offices": OFFICE_SERVICE_URL,
    "payment": PAYMENT_SERVICE_URL,
    "booking": BOOKING_SERVICE_URL,
    "reports": STATISTICS_SERVICE_URL,
}


def authorized_request(domain, *args, **kwargs):
    global current_token

    kwargs["headers"] = {
        **kwargs.get('headers', {}),
        "Authorization": f"Bearer {current_token.get(domain)}"
    }

    result = request(*args, **kwargs)
    if result.status_code != 401:
        return result

    print("re-auth in domain", domain)
    credentials = {"client_id": CLIENT_ID, "client_secret": JWT_SECRET}
    token_response = request("POST", f"http://{domain}/token", json=credentials)
    current_token[domain] = token_response.json()["token"]

    kwargs["headers"]["Authorization"] = f"Bearer {current_token.get(domain)}"
    return request(*args, **kwargs)


class RoleError(Exception):
    pass


def verify_token_from_cookie():
    print("headers:", flask_request.headers)
    auth_header = flask_request.cookies.get("token")
    print("cookies:", flask_request.cookies)
    if auth_header:
        body = jwt.decode(auth_header, USER_JWT_SECRET, algorithms=['HS256'])
        return body
    return None


@app.after_request
def add_cors(response):
    header = response.headers
    header['Access-Control-Allow-Origin'] = f'http://{FRONT_URL}'
    header['Access-Control-Allow-Headers'] = 'Origin, Content-Type'
    header['Access-Control-Allow-Credentials'] = 'true'
    header['Access-Control-Allow-Methods'] = 'HEAD, GET, POST, DELETE, PUT, PATCH'
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
    print("USER:", user)
    if not user:
        return {"error": "bad token"}, 401

    headers = {"user_id": str(user.get("user_id")), "is_admin": str(int(user.get("is_admin")))}

    print("FINDING ROUTE")
    for route, service in ROUTING_TABLE.items():
        if path.startswith(route):
            try:
                result = authorized_request(
                    service,
                    flask_request.method,
                    f"http://{service}/{path}",
                    json=flask_request.json if flask_request.json else None,
                    headers=headers,
                )
            except RequestException as e:
                return {"error": "service is unavailable", "details": str(e)}, 500
            print("FOUND ROUTE", service)
            return result.text, result.status_code, result.headers.items()
    print("NO ROUTE")
    return {"error": 'No route from gateway'}, 400


# Точка входа ##############################

if __name__ == '__main__':
    PORT = os.environ.get("PORT")
    if not PORT:
        print("USING DEFAULT PORT 7779, не задан $PORT")
        PORT = 7779
    app.run(host="0.0.0.0", port=PORT)

