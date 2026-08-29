import sys
sys.path.insert(0,'.')
from qumail_fresh.backend.models import db, EmailMessage, User
from qumail_fresh.backend.app import app
with app.app_context():
    msgs = EmailMessage.query.order_by(EmailMessage.created_at.desc()).limit(50).all()
    for m in msgs:
        sender = User.query.get(m.sender_id)
        recip = User.query.get(m.recipient_id)
        print(f"{m.message_id} | sender={sender.email if sender else m.sender_id} | recipient={recip.email if recip else m.recipient_id} | recipient_address={m.recipient_address} | level={m.level} | status={m.status}")
