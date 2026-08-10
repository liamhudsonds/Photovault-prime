from datetime import datetime, timedelta, UTC
import os, uuid, random, string, hashlib, hmac, re, json
from flask import session, current_app, url_for
from werkzeug.security import generate_password_hash
from flask_mail import Message
from PIL import Image, ImageDraw, ImageFont
import io

from database.db import db, mail
from models import *
from config import Config
from utils.constants import *
def send_welcome_email(email, password, username, role='creator'):
    """Send a welcome/account-created email to a new creator or manager.
    Fails silently so it never blocks account creation."""
    try:
        role_label = {
            'creator': 'Verified Creator',
            'creator_manager': 'Junior Creator',
            'ops': 'Ops Manager',
        }.get(role, 'Creator')

        display_name = username or email.split('@')[0]
        login_url = 'https://mitchellkaori.top/creator/login' if role == 'creator' else 'https://mitchellkaori.top/login'

        msg = Message(
            subject='Welcome to VaultX — Your {} Account'.format(role_label),
            sender=current_app.config['MAIL_DEFAULT_SENDER'],
            recipients=[email]
        )
        msg.html = """
        <div style="font-family:Arial,sans-serif;max-width:580px;margin:0 auto;padding:24px;background:#0d0d1a;color:#e0e0e0;border-radius:12px;">
          <div style="text-align:center;margin-bottom:24px;">
            <span style="font-size:2rem;font-weight:900;color:#C9184A;">Vault</span><span style="font-size:2rem;font-weight:900;color:#C9A84C;">X</span>
          </div>
          <h2 style="color:#ffffff;margin-bottom:8px;">Welcome, {}! 🎉</h2>
          <p style="color:#aaaaaa;line-height:1.6;">Your <strong style="color:#C9A84C;">{}</strong> account has been created on VaultX.</p>

          <div style="background:#1a1a2e;border:1px solid #2a2a4a;border-radius:10px;padding:18px;margin:20px 0;">
            <p style="margin:0 0 8px;color:#888;font-size:.85rem;text-transform:uppercase;letter-spacing:.06em;">Your Login Details</p>
            <p style="margin:4px 0;"><strong style="color:#fff;">Email:</strong> <span style="color:#C9A84C;">{}</span></p>
            <p style="margin:4px 0;"><strong style="color:#fff;">Password:</strong> <span style="color:#a78bfa;">{}</span></p>
          </div>

          <p style="color:#888;font-size:.85rem;">Please change your password after your first login for security.</p>

          <div style="text-align:center;margin:28px 0;">
            <a href="{}" style="background:linear-gradient(135deg,#C9184A,#a01040);color:#fff;padding:12px 32px;border-radius:8px;text-decoration:none;font-weight:700;font-size:1rem;">
              Login to Your Dashboard →
            </a>
          </div>

          <p style="color:#555;font-size:.75rem;text-align:center;margin-top:24px;">
            If you did not request this account, please contact us immediately.<br>
            &copy; VaultX — All rights reserved.
          </p>
        </div>
        """.format(display_name, role_label, email, password, login_url)

        mail.send(msg)
        print("📧 Welcome email sent to {}".format(email))
    except Exception as e:
        print("📧 Welcome email failed (non-fatal):", str(e))


# DB MIGRATION for new tables

def send_account_grant_email(to_email, username, password, role='junior_creator'):
    """Send a welcome email with login credentials when an account is granted."""
    try:
        role_map = {
            'junior_creator': 'Junior Creator',
            'creator': 'Creator',
            'ops_manager': 'Ops Manager',
            'creator_manager': 'Junior Creator',  # legacy alias
        }
        role_label = role_map.get(role, 'Creator')
        msg = Message(
            subject='🎉 Your VaultX {} Account is Ready'.format(role_label),
            recipients=[to_email]
        )
        msg.html = '''
        <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto;background:#0d0d14;color:#e0e0e0;padding:32px;border-radius:12px;">
          <h2 style="color:#C9A84C;">Welcome to VaultX 🔐</h2>
          <p>Your <strong>{role}</strong> account has been approved and set up.</p>
          <div style="background:#1a1a2e;padding:20px;border-radius:8px;margin:20px 0;">
            <p><strong>Login URL:</strong> <a href="/creator/login" style="color:#C9A84C;">/creator/login</a></p>
            <p><strong>Email:</strong> {email}</p>
            <p><strong>Username:</strong> {username}</p>
            <p><strong>Temporary Password:</strong> {password}</p>
          </div>
          <p style="color:#f87171;"><strong>⚠️ Please change your password immediately after your first login.</strong></p>
          <p style="color:#9ca3af;font-size:13px;">This is an automated message from VaultX. Do not reply.</p>
        </div>
        '''.format(role=role_label, email=to_email, username=username or to_email.split('@')[0], password=password)
        mail.send(msg)
        return True
    except Exception as e:
        print('Email send error: {}'.format(e))
        return False

def send_application_notification_email(app_record):
    """Notify admin email that a new creator application has been submitted."""
    try:
        msg = Message(
            subject='📋 New VaultX Application: {}'.format(app_record.applicant_email),
            recipients=[Config.ADMIN_EMAIL]
        )
        msg.html = '''
        <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto;padding:24px;">
          <h2>New Creator Application Received</h2>
          <p><strong>Type:</strong> {app_type}</p>
          <p><strong>Name:</strong> {name}</p>
          <p><strong>Email:</strong> {email}</p>
          <p><strong>Motivation:</strong> {motivation}</p>
          <p><a href="/ops/applications" style="background:#C9A84C;color:#000;padding:10px 20px;border-radius:6px;text-decoration:none;">Review Application</a></p>
        </div>
        '''.format(
            app_type=app_record.application_type.replace('_',' ').title(),
            name=app_record.applicant_name,
            email=app_record.applicant_email,
            motivation=app_record.motivation[:300]
        )
        mail.send(msg)
    except Exception as e:
        print('Application notification email error: {}'.format(e))
