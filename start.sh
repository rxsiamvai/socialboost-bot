#!/bin/bash
python -c "import telebot; b=telebot.TeleBot('8656424951:AAHEUoOikTfN2RW-ztfSzR93ktRdvJvwIpY'); b.remove_webhook()"
python bot.py
