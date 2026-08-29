from flask_sqlalchemy import SQLAlchemy
from datetime import datetime


db = SQLAlchemy()


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    display_name = db.Column(db.String(100), nullable=False)
    pqc_private = db.Column(db.LargeBinary, nullable=True)
    pqc_public = db.Column(db.LargeBinary, nullable=True)


class QuantumKey(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key_id = db.Column(db.String(64), unique=True, nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    peer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    material = db.Column(db.LargeBinary, nullable=False)
    bits = db.Column(db.Integer, nullable=False)
    qber = db.Column(db.Float, nullable=False)
    matching_bases = db.Column(db.Integer, nullable=False)
    eve_probability = db.Column(db.Float, nullable=False)
    consumed = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class EmailMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.String(80), unique=True, nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    recipient_address = db.Column(db.String(255), nullable=False)
    subject = db.Column(db.String(255), nullable=False)
    level = db.Column(db.Integer, nullable=False)
    payload = db.Column(db.Text, nullable=False)
    key_id = db.Column(db.String(64), nullable=True)
    status = db.Column(db.String(30), default='stored', nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
