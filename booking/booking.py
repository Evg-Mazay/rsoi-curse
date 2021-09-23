from base64 import b64encode, b64decode
from time import time
from hashlib import sha224
from functools import wraps
from datetime import datetime
from requests import request

from flask import Flask
from flask import request as flask_request, _request_ctx_stack
from jose import jwt
from jose.exceptions import JWTError
from sqlalchemy import Column, Integer, Text

import database


# Экземпляр приложения
app = Flask(__name__)
JWT_SECRET = "secret"
OFFICE_SERVICE_URL = "localhost:7775"
CAR_SERVICE_URL = "localhost:7774"
PAYMENT_SERVICE_URL = "localhost:7776"


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
    return request(*args, **kwargs)


@app.route("/booking", methods=["POST"])
def new_booking():
    try:
        car_uuid = flask_request.json["car_uuid"]
        user_id = flask_request.json["user_id"]
        cc_number = flask_request.json["payment_data"]["cc_number"]
        price = flask_request.json["payment_data"]["price"]
        booking_start = flask_request.json["booking_start"]
        booking_end = flask_request.json["booking_end"]
        start_office = flask_request.json["start_office"]
        end_office = flask_request.json["end_office"]
    except Exception as e:
        return {"error": "bad body", "details": str(e)}, 400

    # Сходить в payment_service и заплатить
    api_call_result = make_authorized_request(
        "POST", f"http://{PAYMENT_SERVICE_URL}/payment/pay", json={
            "cc_number": cc_number,
            "ammount": price
        }
    )
    if not api_call_result.ok:
        return {"error": "bad api request", "details": api_call_result.text}, 500
    else:
        payment_id = api_call_result.json()["payment_id"]

    # Добавить в расписание машины недоступность
    api_call_result = make_authorized_request(
        "PUT",  f"http://{OFFICE_SERVICE_URL}/offices/cars/{car_uuid}", json={
            "start_time": booking_start,
            "end_time": booking_end,
            "taken_from": start_office,
            "taken_to": end_office,
        }
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

    return {"booking_id": booking_id}, 201


@app.route("/booking/<int:booking_id>", methods=["DELETE"])
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
    api_call_result = make_authorized_request(
        "POST",
        f"http://{PAYMENT_SERVICE_URL}/payment/{payment_id}/reverse"
    )
    if not api_call_result.ok:
        return {"error": "bad api request", "details": api_call_result.text}, 500

    # Удалить в расписании машины доступность
    api_call_result = make_authorized_request(
        "DELETE",
        f"http://{OFFICE_SERVICE_URL}/offices/cars/{car_uuid}",
        json={"taken_from": taken_from, "start_time": start_time}
    )
    if not api_call_result.ok:
        return {"error": "bad api request", "details": api_call_result.text}, 500

    # Устанавливаем статус cancelled на этот букинг
    with database.Session() as s:
        car_booking = s.query(CarBooking).filter(CarBooking.id == booking_id).one()
        if not car_booking:
            return {"error": "car booking not found"}, 404
        car_booking.status = "CANCELLED"

    return {}, 200


@app.route("/booking/<int:booking_id>/finish", methods=["PATCH"])
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


    # Удалить в расписании машины доступность
    api_call_result = make_authorized_request(
        "DELETE",
        f"http://{OFFICE_SERVICE_URL}/offices/cars/{car_uuid}",
        json={"taken_from": taken_from, "start_time": start_time}
    )
    if not api_call_result.ok:
        return {"error": "bad api request", "details": api_call_result.text}, 500

    # Устанавливаем статус FINISHED на этот букинг
    with database.Session() as s:
        car_booking = s.query(CarBooking).filter(CarBooking.id == booking_id).one()
        car_booking.status = "FINISHED"

    return {}, 200


if __name__ == '__main__':
    database.create_schema()
    app.run(host="127.0.0.1", port=7777)
