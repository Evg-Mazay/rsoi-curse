from functools import wraps
from collections import defaultdict

from requests import request
from flask import Flask
from flask import request as flask_request, jsonify
from sqlalchemy import Column, Integer, Text

import database

# Экземпляр приложения
app = Flask(__name__)
JWT_SECRET = "secret"


class Record(database.Base):
    __tablename__ = 'stat_record'
    id = Column(Integer, primary_key=True)
    car_model = Column(Text, nullable=False)
    office = Column(Text, nullable=False)


@app.route('/reports/create_record', methods=["POST"])
def create_record():
    try:
        car_model = flask_request.json["car_model"]
        office = flask_request.json["office"]
    except Exception as e:
        return {"error": "bad body", "details": str(e)}, 400

    with database.Session() as s:
        record = Record(car_model=car_model, office=office)
        s.add(record)

    return {}, 201



@app.route('/reports/booking-by-models', methods=["GET"])
def booking_by_models():
    with database.Session() as s:
        records = s.query(Record).all()

        result = defaultdict(lambda: 0)
        for rec in records:
            result[rec.office] += 1

    return result, 200


@app.route('/reports/booking-by-offices', methods=["GET"])
def booking_by_offices():
    with database.Session() as s:
        records = s.query(Record).all()

        result = defaultdict(lambda: 0)
        for rec in records:
            result[rec.car_model] += 1

    return result, 200

# Точка входа ##############################

if __name__ == '__main__':
    database.create_schema()
    app.run(host="127.0.0.1", port=7778)
