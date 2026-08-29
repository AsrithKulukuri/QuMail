import sqlite3
con = sqlite3.connect('qumail_fresh/qumail.db')
cur = con.cursor()
users = dict(cur.execute('SELECT id, email FROM user').fetchall())
print('User Map:', users)
print('\nAll Messages in DB:')
for row in cur.execute('SELECT id, message_id, sender_id, recipient_id, recipient_address, subject, level, status, created_at FROM email_message ORDER BY id ASC'):
    s_email = users.get(row[2], row[2])
    r_email = users.get(row[3], row[3])
    print(f'Msg #{row[0]}: ID={row[1]} | From={s_email} | To={r_email} (addr: {row[4]}) | Subject="{row[5]}" | Level={row[6]} | Status={row[7]} | Time={row[8]}')
