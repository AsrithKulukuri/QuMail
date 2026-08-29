import email, imaplib, smtplib
from email.message import EmailMessage
from .config import SMTP_HOST, SMTP_PORT, IMAP_HOST, IMAP_PORT, SMTP_USER, SMTP_PASS, IMAP_USER, IMAP_PASS

def send_smtp(recipient: str, subject: str, body: str, headers=None, attachments=None, user_creds=None):
    user = (user_creds and user_creds.get('smtp_user')) or SMTP_USER
    pwd = (user_creds and user_creds.get('smtp_pass')) or SMTP_PASS
    host = (user_creds and user_creds.get('smtp_host')) or SMTP_HOST
    port = int((user_creds and user_creds.get('smtp_port')) or SMTP_PORT)

    if not user or not pwd:
        raise RuntimeError('SMTP credentials are missing. Please set SMTP_USER and SMTP_PASS in environment variables.')

    msg = EmailMessage()
    msg['From'] = user
    msg['To'] = recipient
    msg['Subject'] = subject
    for k, v in (headers or {}).items():
        msg[k] = str(v)
    msg.set_content(body)

    for a in (attachments or []):
        import base64
        data = base64.b64decode(a['data'])
        maintype, _, sub = (a.get('mime') or 'application/octet-stream').partition('/')
        msg.add_attachment(data, maintype=maintype, subtype=sub or 'octet-stream', filename=a.get('name') or 'attachment')

    # Try configured port first, fallback if network block/timeout occurs
    ports_to_try = [port]
    if port == 465 and 587 not in ports_to_try:
        ports_to_try.append(587)
    elif port == 587 and 465 not in ports_to_try:
        ports_to_try.append(465)

    last_err = None
    for p in ports_to_try:
        try:
            if p == 465:
                with smtplib.SMTP_SSL(host, p, timeout=12) as s:
                    s.login(user, pwd)
                    s.send_message(msg)
                    return
            else:
                with smtplib.SMTP(host, p, timeout=12) as s:
                    s.ehlo()
                    s.starttls()
                    s.ehlo()
                    s.login(user, pwd)
                    s.send_message(msg)
                    return
        except Exception as exc:
            last_err = exc

    raise RuntimeError(f"SMTP failed on {host}:{ports_to_try} ({last_err})")

def fetch_imap(limit=20, user_creds=None):
    user = (user_creds and user_creds.get('imap_user')) or IMAP_USER
    pwd = (user_creds and user_creds.get('imap_pass')) or IMAP_PASS
    host = (user_creds and user_creds.get('imap_host')) or IMAP_HOST
    port = int((user_creds and user_creds.get('imap_port')) or IMAP_PORT)

    if not user or not pwd:
        raise RuntimeError('IMAP credentials are missing. Please set IMAP_USER and IMAP_PASS in environment variables.')

    try:
        with imaplib.IMAP4_SSL(host, port, timeout=12) as m:
            m.login(user, pwd)
            m.select('INBOX')
            status, data = m.search(None, 'ALL')
            if status != 'OK':
                raise RuntimeError('IMAP search failed in INBOX')
            ids = data[0].split()[-limit:]
            out = []
            for mid in reversed(ids):
                status, parts = m.fetch(mid, '(RFC822)')
                if status != 'OK' or not parts or not isinstance(parts[0], tuple):
                    continue
                msg = email.message_from_bytes(parts[0][1])
                body = ''
                if msg.is_multipart():
                    for p in msg.walk():
                        if p.get_content_type() == 'text/plain' and not p.get_filename():
                            body = (p.get_payload(decode=True) or b'').decode(errors='replace')
                            break
                else:
                    body = (msg.get_payload(decode=True) or b'').decode(errors='replace')
                out.append({
                    'from': msg.get('From', ''),
                    'to': msg.get('To', ''),
                    'subject': msg.get('Subject', ''),
                    'body': body,
                    'qumail': msg.get('X-QuMail', ''),
                    'qumail_level': msg.get('X-QuMail-Level', ''),
                    'qumail_key_id': msg.get('X-QuMail-Key-ID', ''),
                    'qumail_message_id': msg.get('X-QuMail-Message-ID', ''),
                    'qumail_sender': msg.get('X-QuMail-Sender', ''),
                    'qumail_recipient': msg.get('X-QuMail-Recipient', '')
                })
            return out
    except Exception as exc:
        raise RuntimeError(f"IMAP failed on {host}:{port} ({exc})")
