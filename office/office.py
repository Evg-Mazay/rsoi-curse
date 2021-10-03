from functools import wraps
from collections import defaultdict
import os
from datetime import datetime

from requests import RequestException
from flask import Flask
from flask import request as flask_request, jsonify
from sqlalchemy import Column, Integer, Text

import database
import auth

# Экземпляр приложения
app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False
CLIENT_ID = "office_service"
JWT_SECRET = auth.KNOWN_CLIENTS["office_service"]
current_token = None

CAR_SERVICE_URL = os.environ.get("CAR_SERVICE_URL", "localhost:7774")
MINIMAL_MODE = int(os.environ.get("MINIMAL_MODE", 0))

print("MINIMAL_MODE:", MINIMAL_MODE)
print("CAR_SERVICE_URL:", CAR_SERVICE_URL)

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


def strip_headers(headers):
    allowed_headers = ["Authorization", "Cookie", "Content-Type", "User-Id", "Is-Admin", "Is-Service"]
    return {k: v for k, v in headers.items() if k in allowed_headers}



@app.route('/token', methods=["POST"])
def get_token():
    if not flask_request.json:
        return {"error": "no json"}, 400
    if auth.KNOWN_CLIENTS.get(flask_request.json["client_id"]) != flask_request.json["client_secret"]:
        return {"error": "Неизвестный client_id или неправильный client_secret"}
    token, expire = auth.create_jwt_token(flask_request.json["client_id"], JWT_SECRET)
    return {"token": token, "expire": expire}, 200


@app.route('/offices', methods=["GET"])
@auth.requires_auth(JWT_SECRET)
def get_offices_list():
    with database.Session() as s:
        offices = s.query(RentOffice).all()
        return jsonify([{"id": o.id, "location": o.location} for o in offices])


@app.route('/offices', methods=["POST"])
@auth.check_for_admin
@auth.requires_auth(JWT_SECRET)
def create_office():
    try:
        location = flask_request.json["location"]
    except Exception as e:
        return {"error": "bad body", "details": str(e)}, 400
    with database.Session() as s:
        s.add(RentOffice(location=location))
    return {}, 201


@app.route('/offices/<int:office_id>/cars', methods=["GET"])
@auth.requires_auth(JWT_SECRET)
def get_cars_list(office_id):
    with database.Session() as s:
        office = s.query(RentOffice).filter(RentOffice.id == office_id).one_or_none()
        if not office:
            return {"error": "office not found"}, 404

        car_availabilities = (
            s.query(AvailableCar)
            .filter(AvailableCar.office_id == office_id)
            .order_by(AvailableCar.available_from.desc())
            .all()
        )
        if not car_availabilities:
            return {"office_location": office.location,
                    "available_cars": [],
                    "unavailable_cars": []}, 200

        result = {}
        result["office_location"] = office.location
        result["available_cars"] = [{
            "car_uuid": c.car_uuid, "from": c.available_from
        } for c in car_availabilities if not c.available_to]

        result["unavailable_cars"] = []
        for a in car_availabilities:
            if a.available_to:
                result["unavailable_cars"].append(
                    {"car_uuid": a.car_uuid, "from": a.available_from, "to": a.available_to}
                )


        try:
            cars_response = auth.authorized_request(
                CLIENT_ID, JWT_SECRET,
                "GET", f"http://{CAR_SERVICE_URL}/cars",
                headers=strip_headers(flask_request.headers),
            )
        except RequestException:
            pass
        else:
            if cars_response.ok:
                names = {c["uuid"]: f'{c["brand"]} - {c["model"]}' for c in cars_response.json()}
                for car in result["available_cars"]:
                    car["name"] = names[car["car_uuid"]]
                for car in result["unavailable_cars"]:
                    car["name"] = names[car["car_uuid"]]


        return jsonify(dict(result))


@app.route('/offices/<int:office_id>/cars/<string:car_uuid>', methods=["GET"])
@auth.requires_auth(JWT_SECRET)
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
@auth.requires_auth(JWT_SECRET)
def get_car_availability(car_uuid):
    car_info = None
    try:
        car_info_response = auth.authorized_request(
            CLIENT_ID, JWT_SECRET,
            "GET", f"http://{CAR_SERVICE_URL}/cars/{car_uuid}",
            headers=strip_headers(flask_request.headers),
        )
    except RequestException:
        pass
    else:
        if car_info_response.ok:
            car_info = car_info_response.json()

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
        result["car"] = car_info
        result["offices"] = []
        result["last_available"] = {
            "office_id": car_availabilities[0].office_id, "from": car_availabilities[0].available_from
        }
        for a in car_availabilities[1:]:
            result["offices"].append({"office_id": a.office_id, "from": a.available_from, "to": a.available_to})

        return jsonify(dict(result))


@app.route('/offices/<int:office_id>/cars/<string:car_uuid>', methods=["POST"])
@auth.check_for_admin
@auth.requires_auth(JWT_SECRET)
def add_car_to_office(office_id, car_uuid):
    try:
        available_from = int(flask_request.json["available_from"])
    except Exception as e:
        return {"error": "bad body", "details": str(e)}, 400

    with database.Session() as s:
        if not list(s.query(RentOffice).filter(RentOffice.id == office_id).all()):
            return {"error": "несуществующий office_id"}, 400

        if not MINIMAL_MODE:
            check_car_response = auth.authorized_request(
                CLIENT_ID, JWT_SECRET,
                "GET",
                f"http://{CAR_SERVICE_URL}/cars",
                headers=strip_headers(flask_request.headers)
            )
            if car_uuid not in [c["uuid"] for c in check_car_response.json()]:
                return {"error": "несуществующий car_uuid"}, 400

        s.add(AvailableCar(
            office_id=office_id,
            car_uuid=car_uuid,
            available_from=available_from,
            available_to=None,
        ))
    return {}, 201


@app.route('/offices/<int:office_id>/cars/<string:car_uuid>', methods=["DELETE"])
@auth.check_for_admin
@auth.requires_auth(JWT_SECRET)
def delete_car_from_office(office_id, car_uuid):
    with database.Session() as s:
        car = (
            s.query(AvailableCar)
            .filter(AvailableCar.office_id == office_id)
            .filter(AvailableCar.car_uuid == car_uuid)
            .delete()
        )
        if not car:
            return {"error": "car not found"}, 404
    return {}, 201


@app.route('/offices/cars/<string:car_uuid>/completely', methods=["DELETE"])
@auth.check_for_admin
@auth.requires_auth(JWT_SECRET)
def delete_car_completely(car_uuid):
    del_car_response = auth.authorized_request(
        CLIENT_ID, JWT_SECRET,
        "DELETE",
        f"http://{CAR_SERVICE_URL}/cars/{car_uuid}",
        headers=strip_headers(flask_request.headers)
    )
    if not del_car_response.ok:
        return {"error": "несуществующий car_uuid"}, 404
    with database.Session() as s:
        car = (
            s.query(AvailableCar)
            .filter(AvailableCar.car_uuid == car_uuid)
            .delete()
        )
        if not car:
            return {"error": "car not found"}, 404
    return {}, 201


@app.route('/offices/cars/<string:car_uuid>', methods=["PUT"])
@auth.check_for_service
@auth.requires_auth(JWT_SECRET)
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

        avail_from_str = \
            datetime.fromtimestamp(last_availability.available_from).strftime("%Y-%m-%d")

        if not last_availability:
            return {"error": "car is unavailable"}, 404
        if last_availability.office_id != taken_from:
            return {"error": f"Эта машина освободится "
                             f"только в {last_availability.available_from} ({avail_from_str}) "
                             f"в офисе {last_availability.office_id}"}, 400
        if start_time == end_time:
            return {"error": f"Минимальное время бронирования - 2 дня"}, 400
        if start_time < last_availability.available_from or end_time <= start_time:
            return {"error": f"ошибочное время бронирования, "
                             f"машина доступна с "
                             f"{last_availability.available_from} ({avail_from_str})"}, 400

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
@auth.check_for_service
@auth.requires_auth(JWT_SECRET)
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

    PORT = os.environ.get("PORT")
    if not PORT:
        print("USING DEFAULT PORT 7775, не задан $PORT")
        PORT = 7775
    app.run(host="0.0.0.0", port=PORT)
