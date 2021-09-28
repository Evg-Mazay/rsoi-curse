from functools import wraps
from collections import defaultdict
import os

from requests import request, RequestException
from flask import Flask, redirect
from flask import request as flask_request, jsonify, render_template
from flask_cors import CORS, cross_origin
from sqlalchemy import Column, Integer, Text


# Экземпляр приложения
app = Flask(__name__, template_folder='template')
app.url_map.strict_slashes = False
cors = CORS(app, support_credentials=True)

SESSION_URL = os.environ.get("SESSION_URL", "localhost:7771")
GATEWAY_URL = os.environ.get("GATEWAY_URL", "localhost:7779")

print("SESSION_URL:", SESSION_URL)
print("GATEWAY_URL:", GATEWAY_URL)

context = {
    "sign_in_endpoint": f"http://{SESSION_URL}/auth",
    "register_endpoint": f"http://{SESSION_URL}/register",
    "cars_list_endpoint": f"http://{GATEWAY_URL}/cars",
    "book_endpoint": f"http://{GATEWAY_URL}/booking",
    "offices_endpoint": f"http://{GATEWAY_URL}/offices",
}

def context_with_user():
    return {
        **context,
        "username": flask_request.cookies.get('user'),
        "is_admin": int(flask_request.cookies.get('is_admin', 0))
    }


@app.before_request
def before_request():
    if flask_request.is_secure:
        url = flask_request.url.replace('https://', 'http://', 1)
        return redirect(url)


@app.after_request
def add_cors(response):
    header = response.headers
    header['Access-Control-Allow-Origin'] = '*'
    header['Access-Control-Allow-Headers'] = 'Content-Type'
    header['Access-Control-Allow-Credentials'] = 'true'
    header['Access-Control-Allow-Methods'] = 'OPTIONS, HEAD, GET, POST, DELETE, PUT, PATCH'
    return response


@app.route('/auth', methods=["GET"])
def auth_page():
    return render_template(
        "auth.html", **context_with_user()
    ), 200


@app.route('/', methods=["GET"])
def main_page():
    return render_template(
        "index.html", **context_with_user()
    ), 200


@app.route('/cars', methods=["GET"])
def car_list_page():
    car_list_response = request("GET", f"http://{GATEWAY_URL}/cars", headers=flask_request.headers)

    if not car_list_response.ok:
        if car_list_response.status_code == 401:
            return redirect("/auth")
        return render_template(
            "cars.html",
            **context_with_user(),
            car_list=[{
                "brand": "Ошибка", "model": "сервис машин не отвечает",
                "type": "", "power": car_list_response.status_code
            }]
        ), 200
    return render_template(
        "cars.html",
        **context_with_user(),
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
            **context_with_user(),
            car_info={"car": f"Ошибка: {response.status_code}", "last_available": [], "offices": []}
        ), 200
    return render_template(
        "car_info.html",
        **context_with_user(),
        car_info=response.json()
    ), 200



@app.route('/offices', methods=["GET"])
def office_list_page():
    print("[HEADERS]:", flask_request.headers)
    response = request("GET", f"http://{GATEWAY_URL}/offices", headers=flask_request.headers)
    print("[RESPONSE]:", response.status_code, response.text)

    if not response.ok:
        if response.status_code == 401:
            return redirect("/auth")
        return render_template(
            "offices.html",
            **context_with_user(),
            error=f"Ошибка: [{response.status_code}], {response.text}"
        ), 200
    return render_template(
        "offices.html",
        **context_with_user(),
        error=False,
        offices_list=response.json()
    ), 200



@app.route('/offices/<int:office_id>', methods=["GET"])
def office_page(office_id):
    response = request(
        "GET", f"http://{GATEWAY_URL}/offices/{office_id}/cars", headers=flask_request.headers
    )

    if not response.ok:
        if response.status_code == 401:
            return redirect("/auth")
        return render_template(
            "office_info.html",
            **context_with_user(),
            error=f"Ошибка: [{response.status_code}], {response.text}"
        ), 200
    return render_template(
        "office_info.html",
        **context_with_user(),
        error=False,
        office_info=response.json()
    ), 200




@app.route('/book', methods=["GET"])
def book_page():
    office_id = int(flask_request.args.get("office_id"))
    car_uuid = flask_request.args.get("car_uuid")

    car_name = None
    car_error = False
    car_response = request(
        "GET", f"http://{GATEWAY_URL}/cars/{car_uuid}", headers=flask_request.headers
    )
    if not car_response.ok:
        car_error = True
    else:
        car_name = f"{car_response.json()['brand']} - {car_response.json()['model']}"

    office_name = None
    office_error = False
    office_response = request(
        "GET", f"http://{GATEWAY_URL}/offices", headers=flask_request.headers
    )
    if not office_response.ok:
        office_error = True
    else:
        for office in office_response.json():
            if office["id"] == office_id:
                office_name = office["location"]


    print(car_response.status_code, car_response.text)
    print(office_response.status_code, office_response.text)

    print(office_name, car_name)

    return render_template(
        "book.html",
        **context_with_user(),
        params_info={"office_id": office_id, "car_uuid": car_uuid},
        office_error=office_error,
        car_error=car_error,
        office_data=office_response.json() if office_response.ok else None,
        current_office_name=office_name,
        current_car_name=car_name,
    ), 200



@app.route('/my_books', methods=["GET"])
def my_books():
    auth_header = {"Authorization": f"Bearer {flask_request.cookies.get('token')}"}

    session_response = request("POST", f"http://{SESSION_URL}/verify", headers=auth_header)
    if not session_response.ok:
        return redirect("/auth")
    user_id = session_response.json()['user_id']


    booking_response = request(
        "GET", f"http://{GATEWAY_URL}/booking/user/{user_id}", headers=flask_request.headers
    )
    if not booking_response.ok:
        return render_template(
            "my_books.html",
            **context_with_user(),
            error=booking_response.status_code
        ), 200

    return render_template(
        "my_books.html",
        **context_with_user(),
        book_info=booking_response.json()
    ), 200



@app.route('/stats', methods=["GET"])
def stats():
    try:
        stats_by_offices_response = request(
            "GET", f"http://{GATEWAY_URL}/reports/booking-by-offices", headers=flask_request.headers
        )

        stats_by_uuids_response = request(
            "GET", f"http://{GATEWAY_URL}/reports/booking-by-uuids", headers=flask_request.headers
        )
    except RequestException as e:
        return render_template(
            "my_books.html",
            **context_with_user(),
            error="stats service unavailable: " + str(e),
        ), 200

    car_stats = stats_by_uuids_response.json()

    message = None
    car_service_response = request(
        "GET", f"http://{GATEWAY_URL}/cars", headers=flask_request.headers
    )
    if not car_service_response.ok:
        message = "Недоступен сервис машин, поэтому вместо статистики по моделям" \
                  " - статистика по уникальным машинам"
    else:
        res = defaultdict(lambda: 0)
        models = {c["uuid"]: c["model"] for c in car_service_response.json()}
        for uuid, count in car_stats.items():
            res[models[uuid]] += count
        car_stats = res

    return render_template(
        "stats.html",
        **context_with_user(),
        message=message,
        office_stats=stats_by_offices_response.json(),
        car_stats=car_stats,
    ), 200


# Точка входа ##############################

if __name__ == '__main__':
    PORT = os.environ.get("PORT")
    if not PORT:
        print("USING DEFAULT PORT 7770, не задан $PORT")
        PORT = 7770
    app.run(host="0.0.0.0", port=PORT)
