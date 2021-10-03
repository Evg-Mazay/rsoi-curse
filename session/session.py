from base64 import b64encode, b64decode
from time import time
from hashlib import sha224
from functools import wraps
import os

from flask import Flask
from flask import request, _request_ctx_stack
from flask_cors import CORS, cross_origin
from jose import jwt
from jose.exceptions import JWTError
from sqlalchemy import Column, Integer, Text

import database


# Экземпляр приложения
app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False
cors = CORS(app, support_credentials=True)

JWT_SECRET = "user_jwt_secret"
TOKEN_EXPIRE = 60 * 60 * 1


FRONT_URL = os.environ.get("FRONT_URL", "localhost:7770")
print("FRONT_URL:", FRONT_URL)


class User(database.Base):
    __tablename__ = 'user'
    id = Column(Integer, primary_key=True)
    login = Column(Text, unique=True, nullable=False)
    password_hash = Column(Text, nullable=False)
    role = Column(Text, nullable=False)


@app.after_request
def add_cors(response):
    header = response.headers
    header['Access-Control-Allow-Origin'] = f'http://{FRONT_URL}'
    header['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    header['Access-Control-Allow-Credentials'] = 'true'
    return response


def requires_auth(f):
    @wraps(f)
    def _func(*args, **kwargs):
        auth_data = request.headers.get("Authorization")
        if not auth_data:
            return {"error": "Authorization header missing"}, 401
        if not auth_data.lower().startswith("bearer"):
            return {"error": "only bearer auth supported"}, 401
        auth_data = auth_data[len("bearer"):].strip()

        try:
            jwt_claims = jwt.decode(auth_data, JWT_SECRET, algorithms=['HS256'])
        except JWTError as e:
            return {"error": "bad token", "details": str(e)}, 401

        _request_ctx_stack.top.jwt_claims = jwt_claims
        return f(*args, **kwargs)
    return _func


def requires_admin(f):
    @wraps(f)
    def _func(*args, **kwargs):
        jwt_claims = _request_ctx_stack.top.jwt_claims
        if not jwt_claims.get("is_admin"):
            return {"error": "you are not admin"}, 403
        return f(*args, **kwargs)
    return _func


@app.route("/auth", methods=["POST"])
def get_token():
    print("[headers]", request.headers)
    print("[body]", request.data)
    print("[json]", request.json)

    # auth_data = request.headers.get("Authorization")
    # if not auth_data:
    #     return {"error": "Authorization header missing"}, 400
    # if not auth_data.lower().startswith("basic"):
    #     return {"error": "only basic auth supported"}, 400
    # auth_data = auth_data[len("basic"):].strip()
    #
    # username, password = b64decode(auth_data.encode("utf-8")).decode("utf-8").split(":", 2)
    # username, password = username.strip(), password.strip()

    try:
        username = request.json["login"]
        password = request.json["password"]
    except Exception as e:
        return {"error": "bad body", "details": str(e)}, 400

    with database.Session() as s:
        user = s.query(User).filter(User.login == username).one_or_none()
        if not user:
            return {"error": "user not found"}, 400

        if sha224(password.encode("utf-8")).hexdigest() != user.password_hash:
            return {"error": "invalid credentials"}, 400

        is_admin = user.role == "admin"
        claims = {
            "user_id": user.id,
            "is_admin": is_admin,
            'user': username,
            'exp': int(time()) + TOKEN_EXPIRE,
        }
    token = jwt.encode(claims, JWT_SECRET, algorithm='HS256')
    return {"auth_token": token, "is_admin": int(is_admin)}


@app.route("/verify", methods=["POST"])
@requires_auth
def verify_token():
    decoded_jwt = _request_ctx_stack.top.jwt_claims
    return {"user": decoded_jwt.get("user"), "user_id": decoded_jwt.get("user_id")}


@app.route("/users", methods=["POST"])
@requires_auth
@requires_admin
def add_user():
    try:
        login = request.json["login"]
        password = request.json["password"]
        role = request.json["role"]
    except Exception as e:
        return {"error": "bad body", "details": str(e)}, 400

    try:
        with database.Session() as s:
            user = User(login=login, role=role,
                        password_hash=sha224(password.encode("utf-8")).hexdigest())
            s.add(user)
    except Exception:
        return {"error": "Ошибка регистрации пользователь уже существует"}, 500
    return {"message": "Пользователь зарегистрирован"}, 200


@app.route("/register", methods=["POST"])
def register():
    try:
        login = request.json["login"]
        password = request.json["password"]
    except Exception as e:
        return {"error": "bad body", "details": str(e)}, 400

    try:
        with database.Session() as s:
            user = User(login=login, role="user",
                        password_hash=sha224(password.encode("utf-8")).hexdigest())
            s.add(user)
    except Exception:
        return {"error": "Ошибка регистрации пользователь уже существует"}, 500
    return {"message": "Пользователь зарегистрирован"}, 200


if __name__ == '__main__':
    database.create_schema()

    PORT = os.environ.get("PORT")
    if not PORT:
        print("USING DEFAULT PORT 7771, не задан $PORT")
        PORT = 7771
    app.run(host="0.0.0.0", port=PORT)
