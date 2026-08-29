from backend.app import app

if __name__ == '__main__':
    print('\nQuMail is starting...')
    print('Local:  http://127.0.0.1:5000')
    print('LAN:    http://<YOUR-LAN-IP>:5000')
    app.run(host='0.0.0.0', port=5000, debug=True)
