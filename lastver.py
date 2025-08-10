from flask import Flask, request, jsonify, send_from_directory, render_template_string
from werkzeug.utils import secure_filename
import os
import sqlite3
from PIL import Image
import io
import base64

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

DATABASE = 'ims.db'

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    db = get_db()
    db.execute('''CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE
                  )''')
    db.execute('''CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sender TEXT,
                    receiver TEXT,
                    message TEXT,
                    image_path TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                  )''')
    db.commit()

@app.route('/')
def home():
    return render_template_string("""
        <html>
        <head>
        <title> IMS.NET </title>
        <script>
        let username = "";
        function setUsername() {
            username = document.getElementById('username').value.trim();
            if(username) {
                document.getElementById('chat').style.display = 'block';
                loadMessages();
                setInterval(loadMessages, 5000);
            }
        }
        function sendMessage() {
            let sender = document.getElementById('sender').value.trim();
            let receiver = document.getElementById('receiver').value.trim();
            let message = document.getElementById('message').value.trim();
            fetch('/send', {
                method: 'POST',
                body: new URLSearchParams({sender, receiver, message})
            }).then(r => r.json()).then(d => {
                if(d.status === 'ok') {
                    document.getElementById('message').value = '';
                    loadMessages();
                }
            });
        }
        function loadMessages() {
            fetch('/inbox?username=' + username)
            .then(r => r.json()).then(d => {
                let box = document.getElementById('messages');
                box.innerHTML = '';
                d.messages.forEach(m => {
                    box.innerHTML += `<p><b>${m.sender}:</b> ${m.message || ''} ${(m.image_url) ? '<img src="'+m.image_url+'" width="100">' : ''}</p>`;
                });
            });
        }
        </script>
        </head>
        <body>
            <h1>IMS Chat</h1>
            <input id="username" placeholder="Your username" />
            <button onclick="setUsername()">Enter Chat</button>
            <div id="chat" style="display:none;">
                <input id="sender" placeholder="Sender" />
                <input id="receiver" placeholder="Receiver" />
                <input id="message" placeholder="Type message" />
                <button onclick="sendMessage()">Send</button>
                <div id="messages"></div>
            </div>
        </body>
        </html>
    """)

@app.route('/register', methods=['POST'])
def register():
    username = request.form.get('username', '').strip()
    if not username:
        return jsonify({'status': 'error', 'message': 'Username required'}), 400
    db = get_db()
    try:
        db.execute('INSERT INTO users(username) VALUES (?)', (username,))
        db.commit()
    except sqlite3.IntegrityError:
        pass
    return jsonify({'status': 'ok'})

@app.route('/send', methods=['POST'])
def send_message():
    sender = request.form.get('sender', '').strip()
    receiver = request.form.get('receiver', '').strip()
    message = request.form.get('message', '').strip()
    image_b64 = request.form.get('image', None)
    if not sender or not receiver or (not message and not image_b64):
        return jsonify({'status': 'error', 'message': 'Missing fields'}), 400

    image_path = None
    if image_b64:
        try:
            image_data = base64.b64decode(image_b64)
            image = Image.open(io.BytesIO(image_data))
            image.thumbnail((240, 320))
            filename = f'{sender}_{receiver}_{int(os.times()[4]*1000)}.jpg'
            filename = secure_filename(filename)
            save_path = os.path.join(UPLOAD_FOLDER, filename)
            image.save(save_path, format='JPEG', quality=70)
            image_path = filename
        except Exception:
            return jsonify({'status': 'error', 'message': 'Image decode error'}), 400

    db = get_db()
    db.execute('INSERT INTO messages(sender, receiver, message, image_path) VALUES (?, ?, ?, ?)',
               (sender, receiver, message if message else None, image_path))
    db.commit()
    return jsonify({'status': 'ok'})

@app.route('/inbox', methods=['GET'])
def inbox():
    username = request.args.get('username', '').strip()
    if not username:
        return jsonify({'status': 'error', 'message': 'Username required'}), 400

    db = get_db()
    cursor = db.execute('''
        SELECT sender, message, image_path, timestamp FROM messages
        WHERE receiver = ? ORDER BY timestamp DESC LIMIT 20
    ''', (username,))
    msgs = []
    for row in cursor.fetchall():
        msgs.append({
            'sender': row['sender'],
            'message': row['message'],
            'image_url': f'/uploads/{row["image_path"]}' if row['image_path'] else None,
            'timestamp': row['timestamp']
        })
    return jsonify({'status': 'ok', 'messages': msgs})

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
