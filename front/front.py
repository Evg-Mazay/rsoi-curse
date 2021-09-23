from functools import wraps
from collections import defaultdict

from requests import request
from flask import Flask, redirect
from flask import request as flask_request, jsonify, render_template
from flask_cors import CORS, cross_origin
from sqlalchemy import Column, Integer, Text

import database

# Экземпляр приложения
app = Flask(__name__, template_folder='template')
app.url_map.strict_slashes = False
cors = CORS(app, support_credentials=True)

SESSION_URL = "localhost:7771"
GATEWAY_URL = "localhost:7779"

context = {
    "sign_in_endpoint": f"http://{SESSION_URL}/auth",
    "register_endpoint": f"http://{SESSION_URL}/register",
    "cars_list_endpoint": f"http://{GATEWAY_URL}/cars",
    "book_endpoint": f"http://{GATEWAY_URL}/booking",
}


@app.after_request
def add_cors(response):
    header = response.headers
    header['Access-Control-Allow-Origin'] = '*'
    header['Access-Control-Allow-Headers'] = 'Content-Type'
    header['Access-Control-Allow-Credentials'] = 'true'
    header['Access-Control-Allow-Methods'] = 'OPTIONS, HEAD, GET, POST, DELETE, PUT'
    return response


@app.route('/auth', methods=["GET"])
def auth_page():
    return render_template("auth.html", **context, username=flask_request.cookies.get('user')), 200


@app.route('/', methods=["GET"])
def main_page():
    return render_template("index.html", **context, username=flask_request.cookies.get('user')), 200


@app.route('/cars', methods=["GET"])
def car_list_page():
    car_list_response = request("GET", f"http://{GATEWAY_URL}/cars", headers=flask_request.headers)

    if not car_list_response.ok:
        if car_list_response.status_code == 401:
            return redirect("/auth")
        return render_template(
            "cars.html",
            **context,
            username=flask_request.cookies.get('user'),
            car_list=[{
                "brand": "Ошибка", "model": "сервис машин не отвечает",
                "type": "", "power": car_list_response.status_code
            }]
        ), 200
    return render_template(
        "cars.html",
        **context,
        username=flask_request.cookies.get('user'),
        car_list=car_list_response.json()
    ), 200


@app.route('/cars/<string:car_uuid>', methods=["GET"])
def car_page(car_uuid):
    response = request("GET", f"http://{GATEWAY_URL}/offices/cars/{car_uuid}", headers=flask_request.headers)

    if not response.ok:
        if response.status_code == 401:
            return redirect("/auth")
        return render_template(
            "car_info.html",
            **context,
            username=flask_request.cookies.get('user'),
            car_info={"car": f"Ошибка: {response.status_code}", "last_available": [], "offices": []}
        ), 200
    return render_template(
        "car_info.html",
        **context,
        username=flask_request.cookies.get('user'),
        car_info=response.json()
    ), 200




@app.route('/book', methods=["GET"])
def book_page():
    office_id = flask_request.args.get("office_id")
    car_uuid = flask_request.args.get("car_uuid")

    # office_response = request(
    #     "GET", f"http://{GATEWAY_URL}/offices/{office_id}/cars/{car_uuid}", headers=flask_request.headers
    # )
    # if not office_response.ok:
    #     if office_response.status_code == 401:
    #         return redirect("/auth")

    return render_template(
        "book.html",
        **context,
        username=flask_request.cookies.get('user'),
        params_info={"office_id": office_id, "car_uuid": car_uuid},
        car_info={}
    ), 200



# Точка входа ##############################

if __name__ == '__main__':
    database.create_schema()
    app.run(host="127.0.0.1", port=7770)
