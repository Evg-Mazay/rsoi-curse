from functools import wraps
from uuid import uuid4
import os

from requests import request
from flask import Flask
from flask import request, jsonify
from sqlalchemy import Column, Integer, Text

import database
import auth

# Экземпляр приложения
app = Flask(__name__)
JWT_SECRET = auth.KNOWN_CLIENTS["car_service"]


class Car(database.Base):
    __tablename__ = 'car'
    uuid = Column(Text, primary_key=True)
    brand = Column(Text, nullable=False)
    model = Column(Text, nullable=False)
    power = Column(Integer, nullable=False)
    type = Column(Text, nullable=False)


@app.route('/token', methods=["POST"])
def get_token():
    if not request.json:
        return {"error": "no json"}, 400
    if auth.KNOWN_CLIENTS.get(request.json["client_id"]) != request.json["client_secret"]:
        return {"error": "Неизвестный client_id или неправильный client_secret"}
    token, expire = auth.create_jwt_token(request.json["client_id"], JWT_SECRET)
    return {"token": token, "expire": expire}, 200


@app.route('/cars', methods=["GET"])
@auth.requires_auth(JWT_SECRET)
def get_cars_list():
    result = []
    with database.Session() as s:
        cars = s.query(Car).all()
        for car in cars:
            result.append({
                "uuid": car.uuid,
                "brand": car.brand,
                "model": car.model,
                "type": car.type,
                "power": car.power,
            })
    return jsonify(result)


@app.route('/cars/<string:car_uuid>', methods=["GET"])
@auth.requires_auth(JWT_SECRET)
def get_car(car_uuid):
    with database.Session() as s:
        car = s.query(Car).filter(Car.uuid == car_uuid).one_or_none()
        if not car:
            return {"error": "car not found"}, 404
        return {
                    "uuid": car.uuid,
                    "brand": car.brand,
                    "model": car.model,
                    "type": car.type,
                    "power": car.power,
                }, 200


@app.route('/cars', methods=["POST"])
@auth.check_for_admin
@auth.requires_auth(JWT_SECRET)
def create_new_car():
    try:
        brand = request.json["brand"]
        model = request.json["model"]
        type_ = request.json["type"]
        power = request.json["power"]
    except Exception as e:
        return {"error": "bad body", "details": str(e)}, 400

    with database.Session() as s:
        s.add(Car(uuid=str(uuid4()), brand=brand, model=model, type=type_, power=power))

    return {}, 201



@app.route('/cars/<string:car_uuid>', methods=["DELETE"])
@auth.check_for_admin
@auth.requires_auth(JWT_SECRET)
def delete_car(car_uuid):
    with database.Session() as s:
        car = s.query(Car).filter(Car.uuid == car_uuid).one_or_none()
        if not car:
            return {"error": "car does not exist"}, 400
        s.delete(car)
    return {}, 201




# Точка входа ##############################

if __name__ == '__main__':
    database.create_schema()

    PORT = os.environ.get("PORT")
    if not PORT:
        print("USING DEFAULT PORT 7774, не задан $PORT")
        PORT = 7774
    app.run(host="0.0.0.0", port=PORT)
