from functools import wraps
from collections import defaultdict

from requests import request
from flask import Flask
from flask import request as flask_request, jsonify
from sqlalchemy import Column, Integer, Text

import database

# Экземпляр приложения
app = Flask(__name__)
CLIENT_ID = "office_service"
JWT_SECRET = "office_12345"
current_token = None

CAR_SERVICE_URL = "localhost:7774"


class RentOffice(database.Base):
    __tablename__ = 'rent_office'
    id = Column(Integer, primary_key=True)
    location = Column(Text, nullable=False)


class AvailableCar(database.Base):
    __tablename__ = 'available_car'
    id = Column(Integer, primary_key=True)
    office_id = Column(Integer, nullable=False)
    car_uuid = Column(Text, nullable=False)
    available_from = Column(Integer, nullable=False)
    available_to = Column(Integer, nullable=True)


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


@app.route('/offices', methods=["GET"])
def get_offices_list():
    with database.Session() as s:
        offices = s.query(RentOffice).all()
        return jsonify([{"id": o.id, "location": o.location} for o in offices])


@app.route('/offices/<int:office_id>/cars', methods=["GET"])
def get_cars_list(office_id):
    with database.Session() as s:
        cars_availability = (
            s.query(AvailableCar)
            .filter(AvailableCar.office_id == office_id)
            .all()
        )
        return jsonify([(c.id, c.car_uuid) for c in cars_availability])


@app.route('/offices/<int:office_id>/cars/<string:car_uuid>', methods=["GET"])
def get_car_availability_in_office(office_id, car_uuid):
    with database.Session() as s:
        car_availabilities = (
            s.query(AvailableCar)
            .filter(AvailableCar.office_id == office_id)
            .filter(AvailableCar.car_uuid == car_uuid)
            .order_by(AvailableCar.available_from.desc())
            .all()
        )
        if not car_availabilities:
            return {"error": "car not available in that office"}, 404

        return jsonify([
            {"id": a.id, "from": a.available_from, "to": a.available_to}
            for a in car_availabilities
        ])


@app.route('/offices/cars/<string:car_uuid>', methods=["GET"])
def get_car_availability(car_uuid):
    with database.Session() as s:
        car_availabilities = (
            s.query(AvailableCar)
            .filter(AvailableCar.car_uuid == car_uuid)
            .order_by(AvailableCar.available_from.desc())
            .all()
        )
        if not car_availabilities:
            return {"error": "car not available"}, 404

        result = {}
        result["car"] = None  # request
        result["offices"] = []
        result["last_available"] = {
            "office_id": car_availabilities[0].office_id, "from": car_availabilities[0].available_from
        }
        for a in car_availabilities[1:]:
            result["offices"].append({"office_id": a.office_id, "from": a.available_from, "to": a.available_to})

        return jsonify(dict(result))


@app.route('/offices/<int:office_id>/cars/<string:car_uuid>', methods=["POST"])
def add_car_to_office(office_id, car_uuid):
    with database.Session() as s:
        if not list(s.query(RentOffice).filter(RentOffice.id == office_id).all()):
            return {"error": "несуществующий office_id"}, 400
        if not request("GET", f"{CAR_SERVICE_URL}/cars/{car_uuid}").ok:
            return {"error": "несуществующий car_uuid"}, 400
        s.add(AvailableCar(office_id=office_id, car_uuid=car_uuid))
    return {}, 201


@app.route('/offices/<int:office_id>/cars/<string:car_uuid>', methods=["DELETE"])
def delete_car_from_office(office_id, car_uuid):
    with database.Session() as s:
        car = (
            s.query(AvailableCar)
            .filter(AvailableCar.office_id == office_id)
            .filter(AvailableCar.car_uuid == car_uuid)
            .all()
        )
        if not car:
            return {"error": "car not found"}, 404
        s.delete(car)
    return {}, 201


@app.route('/offices/cars/<string:car_uuid>', methods=["PUT"])
def book(car_uuid):
    try:
        start_time = int(flask_request.json["start_time"])
        end_time = int(flask_request.json["end_time"])
        taken_from = int(flask_request.json["taken_from"])
        taken_to = int(flask_request.json["taken_to"])
    except Exception as e:
        return {"error": "bad body", "details": str(e)}, 400

    with database.Session() as s:
        # ищем последний свободный слот, проверяем совпадает ли его офис с переданным
        last_availability = (
            s.query(AvailableCar)
            .filter(AvailableCar.car_uuid == car_uuid)
            .filter(AvailableCar.available_to == None)
            .one_or_none()
        )
        if not last_availability:
            return {"error": "car is unavailable"}, 404
        if last_availability.office_id != taken_from:
            return {"error": f"Эта машина освободится "
                             f"только в {last_availability.available_from} "
                             f"в офисе {last_availability.office_id}"}, 400
        if start_time < last_availability.available_from or end_time <= start_time:
            return {"error": f"ошибочное время бронирования, "
                             f"машина доступна с {last_availability.available_from}"}, 400

        # У последнего свободного слота ставим дату окончания доступности
        last_availability.available_to = start_time

        # Создаем новый слот в новом офисе
        s.add(AvailableCar(
            office_id=taken_to,
            car_uuid=last_availability.car_uuid,
            available_from=end_time,
            available_to=None,
        ))
    return {}, 201


@app.route('/offices/cars/<string:car_uuid>', methods=["DELETE"])
def delete_car_availability(car_uuid):
    try:
        start_time = int(flask_request.json["start_time"])
        taken_from = int(flask_request.json["taken_from"])
    except Exception as e:
        return {"error": "bad body", "details": str(e)}, 400
    with database.Session() as s:
        availability = (
            s.query(AvailableCar)
            .filter(AvailableCar.available_to == start_time)
            .filter(AvailableCar.office_id == taken_from)
            .filter(AvailableCar.car_uuid == car_uuid)
            .one_or_none()
        )
        if availability:
            s.delete(availability)
        else:
            return {"error": "not found"}, 404
    return {}, 200



# Точка входа ##############################

if __name__ == '__main__':
    database.create_schema()
    app.run(host="127.0.0.1", port=7775)
