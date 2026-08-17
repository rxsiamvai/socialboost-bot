import os
from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "SocialBoost Bot Running 24/7"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()
