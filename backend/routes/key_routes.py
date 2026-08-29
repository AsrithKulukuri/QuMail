from flask import Blueprint, jsonify, request, session
from ..models import db, User, QuantumKey
from ..key_manager import generate_bb84_key
from ..config import KME_ID

bp = Blueprint('keys', __name__)


def require_user():
    uid = session.get('user_id')
    return db.session.get(User, uid) if uid else None


def ensure_pqc(user):
    if user.pqc_private and user.pqc_public:
        return
    from ..encryption_engine import mlkem_generate
    user.pqc_private, user.pqc_public = mlkem_generate()
    db.session.commit()


@bp.post('/api/v1/keys/generate')
def generate_key():
    user = require_user()
    if not user:
        return jsonify(error='Login required'), 401
    data = request.get_json(silent=True) or {}
    key_bits = int(data.get('key_bits', 4096))
    eve = float(data.get('eve_probability', 0.0))
    peer_email = data.get('peer_email')
    peer = User.query.filter_by(email=peer_email.lower()).first() if peer_email else None

    result = generate_bb84_key(key_bits, eve)
    if not result.accepted:
        return jsonify(
            success=False, error='BB84 key rejected because QBER exceeded the threshold',
            qber=round(result.qber * 100, 2), matching_bases=result.matching_bases,
            transmissions=result.total_transmissions, eve_probability=eve
        ), 422

    key_id = f'QK-{QuantumKey.query.count()+1:06d}'
    record = QuantumKey(
        key_id=key_id, owner_id=user.id, peer_id=peer.id if peer else None,
        material=result.key_bytes, bits=key_bits, qber=result.qber * 100,
        matching_bases=result.matching_bases, eve_probability=eve, consumed=False
    )
    db.session.add(record)
    # If a peer was specified, provision an identical copy at the peer side.
    if peer:
        peer_record = QuantumKey(
            key_id=key_id + '-PEER', owner_id=peer.id, peer_id=user.id,
            material=result.key_bytes, bits=key_bits, qber=result.qber * 100,
            matching_bases=result.matching_bases, eve_probability=eve, consumed=False
        )
        db.session.add(peer_record)
    db.session.commit()
    return jsonify(success=True, key={
        'id': key_id, 'bits': key_bits, 'status': 'UNUSED',
        'qber': round(result.qber * 100, 2), 'matching_bases': result.matching_bases,
        'eve_probability': eve, 'kme_id': KME_ID
    })


@bp.get('/api/v1/keys')
def list_keys():
    user = require_user()
    if not user:
        return jsonify(error='Login required'), 401
    keys = QuantumKey.query.filter_by(owner_id=user.id).order_by(QuantumKey.created_at.desc()).all()
    return jsonify(keys=[{
        'id': k.key_id, 'bits': k.bits, 'consumed': k.consumed,
        'qber': k.qber, 'matching_bases': k.matching_bases,
        'eve_probability': k.eve_probability
    } for k in keys])


@bp.post('/api/v1/keys/<key_id>/consume')
def consume(key_id):
    user = require_user()
    if not user:
        return jsonify(error='Login required'), 401
    key = QuantumKey.query.filter_by(key_id=key_id, owner_id=user.id).first()
    if not key:
        return jsonify(error='Key not found'), 404
    if key.consumed:
        return jsonify(error='Key already consumed'), 409
    key.consumed = True
    db.session.commit()
    return jsonify(success=True, id=key.key_id, status='CONSUMED')
