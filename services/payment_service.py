from datetime import datetime, timedelta, UTC
import os, uuid, random, string, hashlib, hmac, re, json
from flask import session, current_app, url_for
from werkzeug.security import generate_password_hash
from flask_mail import Message
from PIL import Image, ImageDraw, ImageFont
import io

from database.db import db, mail
from models import *
from utils.constants import *
def create_binance_signature(timestamp, nonce, body):
    payload   = '{}\n{}\n{}\n'.format(timestamp, nonce, body)
    signature = hmac.new(BINANCE_SECRET_KEY.encode(), payload.encode(), hashlib.sha512).hexdigest().upper()
    return signature
