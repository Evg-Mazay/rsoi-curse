from functools import wraps
from collections import defaultdict
import os

from requests import request
from flask import Flask
from flask import request as flask_request, jsonify
from sqlalchemy import Column, Integer, Text

import database
import auth

# Экземпляр приложения
app = Flask(__name__)
JWT_SECRET = auth.KNOWN_CLIENTS["statistics_service"]


class Record(database.Base):
    __tablename__ = 'stat_record'
    id = Column(Integer, primary_key=True)
    car_uuid = Column(Text, nullable=False)
    office_id = Column(Text, nullable=False)


@app.route('/token', methods=["POST"])
def get_token():
    if not flask_request.json:
        return {"error": "no json"}, 400
    if auth.KNOWN_CLIENTS.get(flask_request.json["client_id"]) != flask_request.json["client_secret"]:
        return {"error": "Неизвестный client_id или неправильный client_secret"}
    token, expire = auth.create_jwt_token(flask_request.json["client_id"], JWT_SECRET)
    return {"token": token, "expire": expire}, 200


@app.route('/reports/create_record', methods=["POST"])
@auth.requires_auth(JWT_SECRET)
def create_record():
    try:
        car_uuid = flask_request.json["car_uuid"]
        office_id = flask_request.json["office_id"]
    except Exception as e:
        return {"error": "bad body", "details": str(e)}, 400

    with database.Session() as s:
        record = Record(car_uuid=car_uuid, office_id=office_id)
        s.add(record)

    return {}, 201



@app.route('/reports/booking-by-uuids', methods=["GET"])
@auth.check_for_admin
@auth.requires_auth(JWT_SECRET)
def booking_by_uuids():
    with database.Session() as s:
        records = s.query(Record).all()

        result = defaultdict(lambda: 0)
        for rec in records:
            result[rec.car_uuid] += 1

    return result, 200


@app.route('/reports/booking-by-offices', methods=["GET"])
@auth.check_for_admin
@auth.requires_auth(JWT_SECRET)
def booking_by_offices():
    with database.Session() as s:
        records = s.query(Record).all()

        result = defaultdict(lambda: 0)
        for rec in records:
            result[rec.office_id] += 1

    return result, 200

# Точка входа ##############################

if __name__ == '__main__':
    database.create_schema()

    PORT = os.environ.get("PORT")
    if not PORT:
        print("USING DEFAULT PORT 7778, не задан $PORT")
        PORT = 7778
    app.run(host="0.0.0.0", port=PORT)
