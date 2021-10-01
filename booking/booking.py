from base64 import b64encode, b64decode
from time import time
from hashlib import sha224
from functools import wraps
from datetime import datetime
from requests import request, RequestException
import os

from flask import Flask
from flask import request as flask_request, _request_ctx_stack, jsonify
from jose import jwt
from jose.exceptions import JWTError
from sqlalchemy import Column, Integer, Text

import database
import auth


# Экземпляр приложения
app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False
CLIENT_ID = "booking_service"
JWT_SECRET = auth.KNOWN_CLIENTS["booking_service"]

OFFICE_SERVICE_URL = os.environ.get("OFFICE_SERVICE_URL", "localhost:7775")
CAR_SERVICE_URL = os.environ.get("CAR_SERVICE_URL", "localhost:7774")
PAYMENT_SERVICE_URL = os.environ.get("PAYMENT_SERVICE_URL", "localhost:7776")
STATISTIC_SERVICE_URL = os.environ.get("STATISTIC_SERVICE_URL", "localhost:7778")

MINIMAL_MODE = int(os.environ.get("MINIMAL_MODE", 0))
print("MINIMAL_MODE:", MINIMAL_MODE)

print("OFFICE_SERVICE_URL:", OFFICE_SERVICE_URL)
print("CAR_SERVICE_URL:", CAR_SERVICE_URL)
print("PAYMENT_SERVICE_URL:", PAYMENT_SERVICE_URL)
print("STATISTIC_SERVICE_URL:", STATISTIC_SERVICE_URL)

class CarBooking(database.Base):
    __tablename__ = 'car_booking'
    id = Column(Integer, primary_key=True)
    car_uuid = Column(Integer, nullable=False)
    user_id = Column(Integer, nullable=False)
    payment_id = Column(Integer, nullable=False)
    booking_start = Column(Integer, nullable=False)
    booking_end = Column(Integer, nullable=False)
    start_office = Column(Integer, nullable=False)
    end_office = Column(Integer, nullable=False)
    status = Column(Text, nullable=False)


def make_authorized_request(*args, **kwargs):
    class FailedResponseMock:
        ok = False
        status_code = 0
        def __init__(self, e):
            self.text = e

    try:
        return auth.authorized_request(*args, **kwargs)
    except RequestException as e:
        return FailedResponseMock(e)


@app.route('/token', methods=["POST"])
def get_token():
    if not flask_request.json:
        return {"error": "no json"}, 400
    if auth.KNOWN_CLIENTS.get(flask_request.json["client_id"]) != flask_request.json["client_secret"]:
        return {"error": "Неизвестный client_id или неправильный client_secret"}
    token, expire = auth.create_jwt_token(flask_request.json["client_id"], JWT_SECRET)
    return {"token": token, "expire": expire}, 200


@app.route("/booking", methods=["POST"])
@auth.requires_auth(JWT_SECRET)
def new_booking():
    try:
        car_uuid = flask_request.json["car_uuid"]
        user_id = flask_request.headers["user_id"]
        cc_number = flask_request.json["payment_data"]["cc_number"]
        price = flask_request.json["payment_data"]["price"]
        booking_start = flask_request.json["booking_start"]
        booking_end = flask_request.json["booking_end"]
        start_office = flask_request.json["start_office"]
        end_office = flask_request.json["end_office"]
    except Exception as e:
        return {"error": "bad body", "details": str(e)}, 400

    print("BOOKING:", booking_start, "-", booking_end)

    # Сходить в payment_service и заплатить
    if not MINIMAL_MODE:
        api_call_result = make_authorized_request(
            CLIENT_ID, JWT_SECRET,
            "POST", f"http://{PAYMENT_SERVICE_URL}/payment/pay", json={
                "cc_number": cc_number,
                "ammount": price
            },
            headers=flask_request.headers
        )
        if not api_call_result.ok:
            return {"error": "bad api request", "details": api_call_result.text}, 500
        else:
            payment_id = api_call_result.json()["payment_id"]
    else:
        payment_id = 0

    # Добавить в расписание машины недоступность
    api_call_result = make_authorized_request(
        CLIENT_ID, JWT_SECRET,
        "PUT",  f"http://{OFFICE_SERVICE_URL}/offices/cars/{car_uuid}", json={
            "start_time": booking_start,
            "end_time": booking_end,
            "taken_from": start_office,
            "taken_to": end_office,
        },
        headers=flask_request.headers
    )
    if not api_call_result.ok:
        return {"error": "bad api request", "details": api_call_result.text}, 500

    # Создать объект в базе
    with database.Session() as s:
        car_booking = CarBooking(
            car_uuid=car_uuid,
            user_id=user_id,
            payment_id=payment_id,
            booking_start=booking_start,
            booking_end=booking_end,
            start_office=start_office,
            end_office=end_office,
            status="NEW"
        )
        s.add(car_booking)
        s.flush()
        booking_id = car_booking.id

    # Записываем в статистику
    if not MINIMAL_MODE:
        api_call_result = make_authorized_request(
            CLIENT_ID, JWT_SECRET,
            "POST", f"http://{STATISTIC_SERVICE_URL}/reports/create_record", json={
                "car_uuid": car_uuid,
                "office_id": start_office,
            },
            headers=flask_request.headers
        )
        if not api_call_result.ok:
            print("ошибка при запросе сервиса статистики:", api_call_result.status_code, api_call_result.text)

    return {"booking_id": booking_id}, 201


@app.route("/booking/<int:booking_id>", methods=["DELETE"])
@auth.requires_auth(JWT_SECRET)
def cancel_booking(booking_id):
    with database.Session() as s:
        car_booking = s.query(CarBooking).filter(CarBooking.id == booking_id).one_or_none()
        if not car_booking:
            return {"error": "car booking not found"}, 404
        if car_booking.status != "NEW":
            return {"error": "this booking is not new"}, 400
        car_uuid = car_booking.car_uuid
        taken_from = car_booking.start_office
        start_time = car_booking.booking_start
        payment_id = car_booking.payment_id

    # Вернуть деньги
    if not MINIMAL_MODE:
        api_call_result = make_authorized_request(
            CLIENT_ID, JWT_SECRET,
            "POST",
            f"http://{PAYMENT_SERVICE_URL}/payment/{payment_id}/reverse",
            headers=flask_request.headers
        )
        if not api_call_result.ok:
            return {"error": "bad api request", "details": api_call_result.text}, 500

    # # Удалить в расписании машины доступность
    # api_call_result = make_authorized_request(
    #     CLIENT_ID, JWT_SECRET,
    #     "DELETE",
    #     f"http://{OFFICE_SERVICE_URL}/offices/cars/{car_uuid}",
    #     json={"taken_from": taken_from, "start_time": start_time},
    #     headers=flask_request.headers
    # )
    # if not api_call_result.ok:
    #     return {"error": "bad api request", "details": api_call_result.text}, 500

    # Устанавливаем статус cancelled на этот букинг
    with database.Session() as s:
        car_booking = s.query(CarBooking).filter(CarBooking.id == booking_id).one()
        if not car_booking:
            return {"error": "car booking not found"}, 404
        car_booking.status = "CANCELLED"

    return {}, 200


@app.route("/booking/<int:booking_id>/finish", methods=["PATCH"])
@auth.requires_auth(JWT_SECRET)
def end_booking(booking_id):
    with database.Session() as s:
        car_booking = s.query(CarBooking).filter(CarBooking.id == booking_id).one_or_none()
        if not car_booking:
            return {"error": "car booking not found"}, 404
        if car_booking.status != "NEW":
            return {"error": "this booking has ended"}, 400
        car_uuid = car_booking.car_uuid
        taken_from = car_booking.start_office
        start_time = car_booking.booking_start


    # # Удалить в расписании машины доступность
    # api_call_result = make_authorized_request(
    #     CLIENT_ID, JWT_SECRET,
    #     "DELETE",
    #     f"http://{OFFICE_SERVICE_URL}/offices/cars/{car_uuid}",
    #     json={"taken_from": taken_from, "start_time": start_time},
    #     headers=flask_request.headers
    # )
    # if not api_call_result.ok:
    #     return {"error": "bad api request", "details": api_call_result.text}, 500

    # Устанавливаем статус FINISHED на этот букинг
    with database.Session() as s:
        car_booking = s.query(CarBooking).filter(CarBooking.id == booking_id).one()
        car_booking.status = "FINISHED"

    return {}, 200


@app.route("/booking/user/<int:user_id>", methods=["GET"])
@auth.requires_auth(JWT_SECRET)
def get_all_books(user_id):
    with database.Session() as s:
        car_bookings = (
            s.query(CarBooking)
            .filter(CarBooking.user_id == user_id)
            .order_by(CarBooking.booking_start.desc())
            .all()
        )
        result = {
            "active": [
                {
                    "id": c.id,
                    "car_uuid": c.car_uuid,
                    "booking_start": c.booking_start,
                    "booking_end": c.booking_end,
                    "start_office": c.start_office,
                    "end_office": c.end_office,
                    "status": c.status,
                }
                for c in car_bookings
                if c.status == "NEW"
            ],
            "done": [
                {
                    "id": c.id,
                    "car_uuid": c.car_uuid,
                    "booking_start": c.booking_start,
                    "booking_end": c.booking_end,
                    "start_office": c.start_office,
                    "end_office": c.end_office,
                    "status": c.status,
                }
                for c in car_bookings
                if c.status != "NEW"
            ]
        }
        return result, 200


if __name__ == '__main__':
    database.create_schema()

    PORT = os.environ.get("PORT")
    if not PORT:
        print("USING DEFAULT PORT 7777, не задан $PORT")
        PORT = 7777
    app.run(host="0.0.0.0", port=PORT)
