from functools import wraps
from collections import defaultdict

from flask import Flask
from flask import request as flask_request, jsonify
from sqlalchemy import Column, Integer, Text

import database
import auth

# Экземпляр приложения
app = Flask(__name__)
JWT_SECRET = auth.KNOWN_CLIENTS["payment_service"]


class Payment(database.Base):
    __tablename__ = 'payment'
    id = Column(Integer, primary_key=True)
    status = Column(Text, nullable=False)
    cc_number = Column(Text, nullable=False)
    price = Column(Integer, nullable=False)


@app.route('/token', methods=["POST"])
def get_token():
    if not flask_request.json:
        return {"error": "no json"}, 400
    if auth.KNOWN_CLIENTS.get(flask_request.json["client_id"]) != flask_request.json["client_secret"]:
        return {"error": "Неизвестный client_id или неправильный client_secret"}
    token, expire = auth.create_jwt_token(flask_request.json["client_id"], JWT_SECRET)
    return {"token": token, "expire": expire}, 200


@app.route('/payment/pay', methods=["POST"])
@auth.requires_auth(JWT_SECRET)
def pay():
    try:
        cc_number = flask_request.json["cc_number"]
        ammount = flask_request.json["ammount"]
    except Exception as e:
        return {"error": "bad body", "details": str(e)}, 400

    # Для теста
    if cc_number == "test_reject":
        with database.Session() as s:
            s.add(Payment(status="REJECTED", cc_number=cc_number, price=ammount))
        return {"reason": "rejected"}, 403

    with database.Session() as s:
        payment = Payment(status="PAID", cc_number=cc_number, price=ammount)
        s.add(payment)
        s.flush()
        payment_id = payment.id

    return {"payment_id": payment_id}, 201



@app.route('/payment/<int:payment_id>/reverse', methods=["POST"])
@auth.requires_auth(JWT_SECRET)
def reverse(payment_id):
    with database.Session() as s:
        payment = s.query(Payment).filter(Payment.id == payment_id).one_or_none()
        if not payment:
            return {"error": "payment not found"}, 404
        payment.status = "REVERSED"

    return {}, 201

# Точка входа ##############################

if __name__ == '__main__':
    database.create_schema()
    app.run(host="127.0.0.1", port=7776)
