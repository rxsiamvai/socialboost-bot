#!/bin/bash
python -c "import telebot; b=telebot.TeleBot('8656424951:AAEFKKgwDdZbGS68SyL68AAqeql_LAp5Nko'); b.remove_webhook()"
python -c "import keep_alive; keep_alive.keep_alive()" &
python bot.py
