import base64
import json
import uuid
from flask import Blueprint, jsonify, request, session
from ..models import db, User, QuantumKey, EmailMessage
from sqlalchemy import or_
from ..config import DEMO_EMAIL_MODE, MAILBOXES
from ..encryption_engine import pack_payload, unpack_payload, otp_encrypt, otp_decrypt, derive_aes_key, aes_encrypt, aes_decrypt, mlkem_encrypt, mlkem_decrypt
from ..email_service import send_smtp, fetch_imap

bp = Blueprint('mail', __name__)


def user():
    uid = session.get('user_id')
    return db.session.get(User, uid) if uid else None


def require_user():
    u = user()
    if not u:
        return None, (jsonify(error='Login required'), 401)
    return u, None


def key_for_send(owner_id, key_id=None):
    q = QuantumKey.query.filter_by(owner_id=owner_id, consumed=False)
    if key_id:
        q = q.filter_by(key_id=key_id)
    return q.order_by(QuantumKey.created_at.asc()).first()


def key_for_receive(owner_id, key_id):
    return QuantumKey.query.filter_by(owner_id=owner_id, key_id=key_id, consumed=False).first()


def encode_attachment(file_obj):
    raw = file_obj.read()
    return {'name': file_obj.filename, 'mime': file_obj.mimetype or 'application/octet-stream', 'data': base64.b64encode(raw).decode()}


@bp.post('/api/mail/send')
def send_mail():
    sender, err = require_user()
    if err:
        return err

    data = request.get_json(silent=True) or {}

    # ---------------------------------------------------------
    # 1. Get the QuMail recipient
    # ---------------------------------------------------------
    qumail_recipient_address = data.get('recipient', '').strip().lower()

    recipient = User.query.filter_by(email=qumail_recipient_address).first()

    if not recipient:
        return jsonify(
            error='Recipient must be a registered QuMail user for this prototype'
        ), 400

    # ---------------------------------------------------------
    # 2. Resolve QuMail identity -> real email address
    #
    # Example:
    # bob@qumail.demo
    #       ↓
    # srujanasruji2105@gmail.com
    # ---------------------------------------------------------
    # Resolve QuMail identity -> real email address using configured mapping
    real_recipient_address = qumail_recipient_address

    mapped_address = MAILBOXES.get(qumail_recipient_address)
    if mapped_address:
        real_recipient_address = mapped_address.strip().lower()

    # ---------------------------------------------------------
    # 3. Basic message data
    # ---------------------------------------------------------
    subject = data.get('subject', '(No subject)')
    body = data.get('body', '')
    level = int(data.get('level', 4))
    attachments = data.get('attachments', [])

    raw = pack_payload(body, attachments)

    key_id = None

    envelope = {
        'version': 1,
        'level': level
    }

    # ---------------------------------------------------------
    # 4. LEVEL 1 — One-Time Pad
    # ---------------------------------------------------------
    if level == 1:

        key = key_for_send(
            sender.id,
            data.get('key_id')
        )

        if not key:
            return jsonify(
                error='No unused BB84 key available. Generate a key first.'
            ), 409

        try:
            envelope['crypto'] = otp_encrypt(
                raw,
                key.material
            )

        except ValueError as exc:
            return jsonify(error=str(exc)), 409

        key_id = key.key_id

        # OTP key is consumed after encryption.
        key.consumed = True

    # ---------------------------------------------------------
    # 5. LEVEL 2 — Quantum-aided AES
    # ---------------------------------------------------------
    elif level == 2:

        key = key_for_send(
            sender.id,
            data.get('key_id')
        )

        if not key:
            return jsonify(
                error='No unused BB84 key available. Generate a key first.'
            ), 409

        envelope['crypto'] = aes_encrypt(
            raw,
            derive_aes_key(key.material)
        )

        key_id = key.key_id

        # Quantum key consumed after use.
        key.consumed = True

    # ---------------------------------------------------------
    # 6. LEVEL 3 — ML-KEM / Post-Quantum
    # ---------------------------------------------------------
    elif level == 3:

        if not recipient.pqc_public:
            return jsonify(
                error='Recipient has no ML-KEM public key'
            ), 409

        envelope['crypto'] = mlkem_encrypt(
            raw,
            recipient.pqc_public
        )

    # ---------------------------------------------------------
    # 7. LEVEL 4 — Standard / No application encryption
    # ---------------------------------------------------------
    elif level == 4:

        envelope['crypto'] = {
            'plaintext': raw.decode()
        }

    else:
        return jsonify(
            error='Security level must be 1, 2, 3, or 4'
        ), 400

    # ---------------------------------------------------------
    # 8. Create QuMail message ID
    # ---------------------------------------------------------
    message_id = (
        'QM-' +
        uuid.uuid4().hex[:16].upper()
    )

    payload = json.dumps(
        envelope,
        separators=(',', ':')
    )

    # ---------------------------------------------------------
    # 9. Store message locally
    #
    # IMPORTANT:
    # recipient_address remains the QuMail identity.
    # ---------------------------------------------------------
    # Debug: log sender/recipient for diagnosis
    try:
        print(f"[QuMail] send_mail: sender={sender.email} recipient={recipient.email} recipient_lookup_address={qumail_recipient_address}")
    except Exception:
        print(f"[QuMail] send_mail: sender_id={sender.id} recipient_id_lookup={qumail_recipient_address}")

    record = EmailMessage(
        message_id=message_id,
        sender_id=sender.id,
        recipient_id=recipient.id,

        # Keep logical QuMail recipient
        recipient_address=qumail_recipient_address,

        subject=subject,
        level=level,
        payload=payload,
        key_id=key_id,
        status='stored'
    )

    db.session.add(record)
    db.session.commit()

    # ---------------------------------------------------------
    # 10. Send through REAL SMTP
    # ---------------------------------------------------------
    sent_externally = False
    external_error = None

    if not DEMO_EMAIL_MODE:

        try:

            send_smtp(
                # IMPORTANT:
                # Send to the REAL Gmail address,
                # NOT bob@qumail.demo
                real_recipient_address,

                subject,
                payload,

                headers={
                    'X-QuMail': '1',

                    'X-QuMail-Level': str(level),

                    'X-QuMail-Key-ID':
                        key_id or '',

                    'X-QuMail-Message-ID':
                        message_id,

                    # Logical QuMail identities
                    'X-QuMail-Sender':
                        sender.email,

                    'X-QuMail-Recipient':
                        qumail_recipient_address,

                    # Actual external destination
                    'X-QuMail-External-Recipient':
                        real_recipient_address
                }
            )

            record.status = 'sent'
            db.session.commit()

            sent_externally = True

        except Exception as exc:

            external_error = str(exc)

    # ---------------------------------------------------------
    # 11. Return result to GUI
    # ---------------------------------------------------------
    return jsonify(
        success=True,

        message_id=message_id,

        level=level,

        key_id=key_id,

        # Useful for debugging/demo
        qumail_recipient=qumail_recipient_address,

        external_recipient=real_recipient_address,

        external_sent=sent_externally,

        external_error=external_error,

        demo_mode=DEMO_EMAIL_MODE
    )

@bp.get('/api/mail/inbox')
def inbox():
    u, err = require_user()
    if err: return err
    # Primary: messages addressed to this user's id.
    # Fallback: also include messages whose stored recipient_address matches
    # the user's email (handles cases where recipient_id may be incorrect).
    rows = EmailMessage.query.filter(
        or_(EmailMessage.recipient_id == u.id, EmailMessage.recipient_address == u.email)
    ).order_by(EmailMessage.created_at.desc()).all()
    return jsonify(messages=[{
        'id': m.message_id,
        'from': db.session.get(User, m.sender_id).email if db.session.get(User, m.sender_id) else 'unknown',
        'to': m.recipient_address, 'subject': m.subject, 'level': m.level,
        'key_id': m.key_id, 'status': m.status, 'encrypted': m.level != 4,
        'created_at': m.created_at.isoformat()
    } for m in rows])


@bp.get('/api/mail/sent')
def sent():
    u, err = require_user()
    if err: return err
    rows = EmailMessage.query.filter_by(sender_id=u.id).order_by(EmailMessage.created_at.desc()).all()
    return jsonify(messages=[{
        'id': m.message_id,
        'from': u.email,
        'to': m.recipient_address, 'subject': m.subject, 'level': m.level,
        'key_id': m.key_id, 'status': m.status, 'encrypted': m.level != 4,
        'created_at': m.created_at.isoformat()
    } for m in rows])



@bp.post('/api/mail/decrypt')
def decrypt_mail():
    u, err = require_user()
    if err: return err
    data = request.get_json(silent=True) or {}
    message = EmailMessage.query.filter_by(message_id=data.get('message_id'), recipient_id=u.id).first()
    if not message:
        return jsonify(error='Message not found'), 404
    envelope = json.loads(message.payload)
    level = message.level
    if level == 1:
        key = key_for_receive(u.id, message.key_id + '-PEER')
        if not key:
            return jsonify(error='Matching unused OTP key not available at recipient KME'), 409
        raw = otp_decrypt(envelope['crypto'], key.material)
        key.consumed = True
    elif level == 2:
        key = key_for_receive(u.id, message.key_id + '-PEER')
        if not key:
            return jsonify(error='Matching unused QKD key not available at recipient KME'), 409
        raw = aes_decrypt(envelope['crypto'], derive_aes_key(key.material))
        key.consumed = True
    elif level == 3:
        if not u.pqc_private:
            return jsonify(error='Recipient ML-KEM private key is unavailable'), 409
        raw = mlkem_decrypt(envelope['crypto'], u.pqc_private)
    else:
        raw = envelope['crypto']['plaintext'].encode()
    db.session.commit()
    data = unpack_payload(raw)
    return jsonify(success=True, message_id=message.message_id, level=level,
                   body=data.get('body', ''), attachments=data.get('attachments', []))




@bp.post('/api/mail/sync')
def sync_external():
    """Pull QuMail messages from the configured IMAP mailbox into the local store."""
    u, err = require_user()
    if err: return err
    try:
        external = fetch_imap()
    except Exception as exc:
        return jsonify(success=False, error=str(exc)), 502
    imported = 0
    for x in external:
        mid = x.get('qumail_message_id')
        if not mid or x.get('qumail') != '1':
            continue
        if EmailMessage.query.filter_by(message_id=mid).first():
            continue
        recipient = x.get('qumail_recipient','').strip().lower()
        if recipient != u.email.lower():
            continue
        sender = User.query.filter_by(email=x.get('qumail_sender','').strip().lower()).first()
        if not sender:
            continue
        try:
            envelope = json.loads(x.get('body',''))
        except Exception:
            continue
        try: level=int(x.get('qumail_level') or envelope.get('level',4))
        except Exception: level=4
        db.session.add(EmailMessage(message_id=mid, sender_id=sender.id, recipient_id=u.id,
            recipient_address=u.email, subject=x.get('subject') or '(No subject)', level=level,
            payload=x.get('body',''), key_id=x.get('qumail_key_id') or None, status='synced'))
        imported += 1
    if imported: db.session.commit()
    return jsonify(success=True, imported=imported)

@bp.get('/api/mail/external-inbox')
def external_inbox():
    u, err = require_user()
    if err: return err
    try:
        return jsonify(success=True, messages=fetch_imap())
    except Exception as exc:
        return jsonify(success=False, error=str(exc)), 502


@bp.get('/api/_debug/messages')
def _debug_messages():
    """Debug endpoint: return recent EmailMessage rows with resolved emails.
    Public for local/demo debugging only. Remove or secure for production."""
    rows = EmailMessage.query.order_by(EmailMessage.created_at.desc()).limit(50).all()
    out = []
    for m in rows:
        sender = db.session.get(User, m.sender_id)
        recip = db.session.get(User, m.recipient_id)
        out.append({
            'message_id': m.message_id,
            'sender_id': m.sender_id,
            'sender_email': sender.email if sender else None,
            'recipient_id': m.recipient_id,
            'recipient_email': recip.email if recip else None,
            'recipient_address': m.recipient_address,
            'level': m.level,
            'status': m.status,
            'created_at': m.created_at.isoformat()
        })
    return jsonify(messages=out)
