from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO
from telegram import Update
from telegram.ext import Updater, MessageHandler, Filters, CallbackContext
from datetime import datetime
import threading
import json
import os
import pytz
import logging
import time

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

seen_messages = set()
MESSAGES_FILE = 'messages.json'

# In-memory cache of messages for fast access
messages_cache = []

BOT_TOKEN = "8006470322:AAFkgKVRAHSxzltEnNUG2De_Bv243BXr2Ck"

def load_messages():
    if os.path.exists(MESSAGES_FILE):
        try:
            with open(MESSAGES_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                logging.info(f"Loaded {len(data)} messages from file.")
                return data
        except Exception as e:
            logging.error(f"Error loading messages: {e}")
            return []
    return []

def save_messages():
    # Save cache to file
    try:
        with open(MESSAGES_FILE, 'w', encoding='utf-8') as f:
            json.dump(messages_cache, f, indent=4)
        logging.info(f"Saved {len(messages_cache)} messages to file.")
    except Exception as e:
        logging.error(f"Error saving messages: {e}")

def append_message(message_data):
    messages_cache.append(message_data)
    # Save asynchronously to avoid blocking SocketIO thread
    threading.Thread(target=save_messages, daemon=True).start()

def handle_message(update: Update, context: CallbackContext):
    message = update.message
    if not message or not message.text:
        logging.warning("Received empty or invalid message")
        return

    if message.message_id not in seen_messages:
        seen_messages.add(message.message_id)

        sender = "Silvara AI"
        if message.from_user:
            sender = message.from_user.first_name or message.from_user.username or "Unknown"

        utc_dt = message.date.replace(tzinfo=pytz.UTC) if message.date else datetime.now(pytz.UTC)
        local_tz = pytz.timezone('Asia/Kolkata')
        local_dt = utc_dt.astimezone(local_tz)

        formatted_date = local_dt.strftime('%Y-%m-%d')
        formatted_time = local_dt.strftime('%H:%M:%S')

        message_data = {
            "sender": sender,
            "text": message.text,
            "date": formatted_date,
            "time": formatted_time
        }

        logging.info(f"New message from {sender} on {formatted_date} at {formatted_time}")

        append_message(message_data)
        socketio.emit('new_message', message_data)

def start_telegram_bot():
    try:
        updater = Updater(BOT_TOKEN, use_context=True)
        dp = updater.dispatcher
        dp.add_handler(MessageHandler(Filters.text & (~Filters.command), handle_message))
        updater.start_polling()
        logging.info("Telegram bot started polling")
    except Exception as e:
        logging.error(f"Error starting Telegram bot: {e}")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/messages')
def get_messages():
    # Return the cache instead of reading file every time
    filtered = [m for m in messages_cache if m.get('date') and m.get('sender') and m.get('text')]
    return jsonify({'messages': filtered})

if __name__ == '__main__':
    # Load existing messages into cache at startup
    messages_cache.extend(load_messages())
    threading.Thread(target=start_telegram_bot, daemon=True).start()
    socketio.run(app, host='0.0.0.0', port=5000)
