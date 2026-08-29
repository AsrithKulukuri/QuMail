import sys, json
sys.path.insert(0,'.')
import requests
base='http://127.0.0.1:5000'
out={}
for user,passw in [('alice@qumail.demo','alice123'),('bob@qumail.demo','bob123')]:
    s=requests.Session()
    r=s.post(base+'/api/login',json={'email':user,'password':passw})
    inbox = s.get(base+'/api/mail/inbox').json()
    out[user] = {'login_status': r.status_code, 'messages': inbox.get('messages')}
with open('qumail_fresh/scripts/check_inboxes_out.json','w') as f:
    json.dump(out,f,indent=2)
print('WROTE')
