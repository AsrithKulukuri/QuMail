import email, imaplib, smtplib
from email.message import EmailMessage
from .config import SMTP_HOST, SMTP_PORT, IMAP_HOST, IMAP_PORT, SMTP_USER, SMTP_PASS, IMAP_USER, IMAP_PASS

def send_smtp(recipient: str, subject: str, body: str, headers=None, attachments=None):
    if not SMTP_USER or not SMTP_PASS: raise RuntimeError('SMTP credentials are not configured in .env')
    msg=EmailMessage(); msg['From']=SMTP_USER; msg['To']=recipient; msg['Subject']=subject
    for k,v in (headers or {}).items(): msg[k]=str(v)
    msg.set_content(body)
    for a in attachments or []:
        import base64
        data=base64.b64decode(a['data']); maintype,_,sub=(a.get('mime') or 'application/octet-stream').partition('/')
        msg.add_attachment(data,maintype=maintype,subtype=sub or 'octet-stream',filename=a.get('name') or 'attachment')
    with smtplib.SMTP_SSL(SMTP_HOST,SMTP_PORT,timeout=20) as s:
        s.login(SMTP_USER,SMTP_PASS); s.send_message(msg)

def fetch_imap(limit=20):
    if not IMAP_USER or not IMAP_PASS: raise RuntimeError('IMAP credentials are not configured in .env')
    with imaplib.IMAP4_SSL(IMAP_HOST,IMAP_PORT,timeout=20) as m:
        m.login(IMAP_USER,IMAP_PASS); m.select('INBOX'); status,data=m.search(None,'ALL')
        if status!='OK': raise RuntimeError('IMAP search failed')
        ids=data[0].split()[-limit:]; out=[]
        for mid in reversed(ids):
            status,parts=m.fetch(mid,'(RFC822)')
            if status!='OK' or not parts or not isinstance(parts[0],tuple): continue
            msg=email.message_from_bytes(parts[0][1]); body=''
            if msg.is_multipart():
                for p in msg.walk():
                    if p.get_content_type()=='text/plain' and not p.get_filename():
                        body=(p.get_payload(decode=True) or b'').decode(errors='replace'); break
            else: body=(msg.get_payload(decode=True) or b'').decode(errors='replace')
            out.append({'from':msg.get('From',''),'to':msg.get('To',''),'subject':msg.get('Subject',''),'body':body,
                        'qumail':msg.get('X-QuMail',''),'qumail_level':msg.get('X-QuMail-Level',''),
                        'qumail_key_id':msg.get('X-QuMail-Key-ID',''),'qumail_message_id':msg.get('X-QuMail-Message-ID',''),
                        'qumail_sender':msg.get('X-QuMail-Sender',''),'qumail_recipient':msg.get('X-QuMail-Recipient','')})
        return out
