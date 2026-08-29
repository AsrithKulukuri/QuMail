from flask import Blueprint, jsonify, request, session
from ..models import db, User

bp = Blueprint('auth', __name__)


def current_user():
    uid = session.get('user_id')
    return db.session.get(User, uid) if uid else None


@bp.post('/api/login')
def login():
    data = request.get_json(silent=True) or {}
    user = User.query.filter_by(email=data.get('email', '').strip().lower()).first()
    if not user or user.password != data.get('password', ''):
        return jsonify(success=False, error='Invalid QuMail credentials'), 401
    session['user_id'] = user.id
    return jsonify(success=True, user={'id': user.id, 'email': user.email, 'name': user.display_name})


@bp.post('/api/logout')
def logout():
    session.clear()
    return jsonify(success=True)


@bp.get('/api/me')
def me():
    user = current_user()
    if not user:
        return jsonify(authenticated=False)
    return jsonify(authenticated=True, user={'id': user.id, 'email': user.email, 'name': user.display_name})
