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


class Payment(database.Base):
    __tablename__ = 'payment'
    id = Column(Integer, primary_key=True)
    status = Column(Text, nullable=False)
    cc_number = Column(Text, nullable=False)
    price = Column(Integer, nullable=False)


@app.route('/payment/pay', methods=["POST"])
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
