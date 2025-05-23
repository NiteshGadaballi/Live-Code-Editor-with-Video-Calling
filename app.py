import os
from dotenv import load_dotenv
from flask import Flask, render_template, request, abort
from twilio.jwt.access_token import AccessToken
from twilio.jwt.access_token.grants import VideoGrant, ChatGrant
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
import requests
import subprocess
from flask_socketio import SocketIO

load_dotenv()
twilio_account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
twilio_api_key_sid = os.environ.get('TWILIO_API_KEY_SID')
twilio_api_key_secret = os.environ.get('TWILIO_API_KEY_SECRET')
twilio_client = Client(twilio_api_key_sid, twilio_api_key_secret,
                       twilio_account_sid)

app = Flask(__name__)
ngrok_url = None
socketio = SocketIO(app)

def start_ngrok():
    """Start ngrok and get the public URL."""
    global ngrok_url
    if not ngrok_url:
        # Start ngrok
        subprocess.Popen(["ngrok", "http", "5000"])

        # Wait for ngrok to start
        import time
        time.sleep(2)

        # Fetch the ngrok public URL
        response = requests.get("http://localhost:4040/api/tunnels")
        data = response.json()
        ngrok_url = data["tunnels"][0]["public_url"]
        print(f"ngrok URL: {ngrok_url}")
    return ngrok_url

@app.route('/')
def index():
    url = start_ngrok()
    return render_template('index.html', ngrok_url=url)

@app.route('/get-token', methods=['POST'])
def get_token():
    identity = request.json.get('identity')
    if not identity:
        return jsonify({'error': 'Identity is required!'}), 400


def get_chatroom(name):
    for conversation in twilio_client.conversations.conversations.stream():
        if conversation.friendly_name == name:
            return conversation

    # a conversation with the given name does not exist ==> create a new one
    return twilio_client.conversations.conversations.create(
        friendly_name=name)





@app.route('/login', methods=['POST'])
def login():
    username = request.get_json(force=True).get('username')
    if not username:
        abort(401)

    conversation = get_chatroom('My Room')
    try:
        conversation.participants.create(identity=username)
    except TwilioRestException as exc:
        # do not error if the user is already in the conversation
        if exc.status != 409:
            raise

    token = AccessToken(twilio_account_sid, twilio_api_key_sid,
                        twilio_api_key_secret, identity=username)
    token.add_grant(VideoGrant(room='My Room'))
    token.add_grant(ChatGrant(service_sid=conversation.chat_service_sid))

    return {'token': token.to_jwt(),
            'conversation_sid': conversation.sid}
            


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)

