import pytest
from backend.encryption_engine import pack_payload, unpack_payload, otp_encrypt, otp_decrypt, derive_aes_key, aes_encrypt, aes_decrypt

def test_payload_roundtrip():
    raw=pack_payload('hello',[{'name':'x.txt','mime':'text/plain','data':'aGVsbG8='}])
    assert unpack_payload(raw)['body']=='hello'

def test_otp_roundtrip_and_short_key():
    raw=b'hello'; key=b'0123456789'
    assert otp_decrypt(otp_encrypt(raw,key),key)==raw
    with pytest.raises(ValueError): otp_encrypt(raw,b'x')

def test_aes_roundtrip():
    raw=b'quantum secure email'; key=derive_aes_key(b'k'*64)
    assert aes_decrypt(aes_encrypt(raw,key),key)==raw
