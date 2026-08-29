import pytest
from backend.app import create_app
from backend.models import db

@pytest.fixture
def client(tmp_path, monkeypatch):
    app=create_app(); app.config.update(TESTING=True, SQLALCHEMY_DATABASE_URI=f'sqlite:///{tmp_path}/test.db')
    with app.app_context():
        db.drop_all(); db.create_all();
        from backend.app import seed
        seed()
    return app.test_client()

def login(c,email='alice@qumail.demo',password='alice123'):
    return c.post('/api/login',json={'email':email,'password':password})

def test_login_and_status(client):
    assert login(client).status_code==200
    assert client.get('/api/status').status_code==200
    assert client.get('/api/v1/keys').status_code==200

def test_bb84_key_generation(client):
    assert login(client).status_code==200
    r=client.post('/api/v1/keys/generate',json={'key_bits':1024,'eve_probability':0,'peer_email':'bob@qumail.demo'})
    assert r.status_code==200
    assert r.get_json()['key']['status']=='UNUSED'

def test_all_mail_levels(client):
    assert login(client).status_code==200
    # L1/L2 need keys; generate two 4096-bit records to cover normal payloads.
    for _ in range(2):
        r=client.post('/api/v1/keys/generate',json={'key_bits':4096,'eve_probability':0,'peer_email':'bob@qumail.demo'})
        assert r.status_code==200, r.get_json()
    for level in (1,2,3,4):
        r=client.post('/api/mail/send',json={'recipient':'bob@qumail.demo','subject':f'L{level}','body':'hello','level':level})
        assert r.status_code==200, (level,r.get_json())

def test_logout(client):
    login(client); assert client.post('/api/logout').status_code==200
