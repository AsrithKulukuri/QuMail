Login details 
mail:alice@qumail.demo and password:alice123
mail:bob@qumail.com and password:bob123
# QuMail — SIH25179 Working Prototype

QuMail is an application-layer secure email prototype built around the architecture in the SIH problem statement. The GUI remains the primary `frontend/Qumail_Server.html` design, while Flask provides the API, SQLite stores demo state, the KME exposes an ETSI GS QKD 014-style REST surface, and Python's SMTP/IMAP standard-library clients provide compatibility with existing mail infrastructure.

## Security levels
1. **L1 — Quantum Secure OTP:** simulated BB84-derived key material XORs the application payload. Sender and recipient key records are one-time-use and consumed after encryption/decryption.
2. **L2 — Quantum-aided AES:** BB84-derived material is passed through HKDF-SHA256 to derive an AES-256-GCM key.
3. **L3 — Post-Quantum Hybrid:** ML-KEM-512 encapsulates an AES session key; AES-GCM encrypts the message.
4. **L4 — Standard:** plaintext application payload; if real-mail mode is enabled, SMTP/TLS protects transport.

BB84 is explicitly a **software simulation**. It models random bits/bases, basis sifting, optional intercept-resend Eve, and QBER sampling. It is not physical QKD hardware.

## Run on Windows
```powershell
py -3.11 -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python run.py
```
Open `http://127.0.0.1:5000`.

Demo accounts:
- `alice@qumail.demo` / `alice123`
- `bob@qumail.demo` / `bob123`

## Real Gmail
Set `DEMO_EMAIL_MODE=false` in `.env`, then configure SMTP/IMAP with a Gmail App Password. Never use or commit the normal Gmail password.

```env
DEMO_EMAIL_MODE=false
SMTP_USER=your-demo-account@gmail.com
SMTP_PASS=your-16-char-app-password
IMAP_USER=your-demo-account@gmail.com
IMAP_PASS=your-16-char-app-password
```

For a real two-mailbox demo, run a QuMail instance for each mailbox or extend the mailbox routing configuration. The **Sync Mail** button pulls QuMail-tagged messages from the configured IMAP inbox and imports them into the local QuMail database.

## API
- `POST /api/login`
- `POST /api/logout`
- `GET /api/me`
- `GET /api/status`
- `POST /api/v1/keys/generate`
- `GET /api/v1/keys`
- `POST /api/v1/keys/<id>/consume`
- `POST /api/mail/send`
- `GET /api/mail/inbox`
- `POST /api/mail/decrypt`
- `POST /api/mail/sync`
- `GET /api/mail/external-inbox`

## Verification
Run from the project root:
```powershell
pytest -v
```
If PowerShell cannot find `backend` during test collection, make sure you are in the folder containing `run.py`, `backend/`, and `tests/`, and run `python -m pytest -v`.
