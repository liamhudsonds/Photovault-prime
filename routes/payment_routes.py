"""VaultX payment routes."""
from flask import Blueprint, current_app

from flask import (
    Flask, render_template, request, flash, jsonify, session,
    redirect, url_for, send_file, abort, send_from_directory,
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_mail import Message
from datetime import datetime, timedelta, UTC
import os, uuid, stripe, hashlib, hmac, time, json, requests, errno, random, string, io, re
from PIL import Image, ImageDraw, ImageFont

from database.db import db, mail, download_tokens
from models import *
from utils.decorators import (
    admin_required, manager_required, ops_manager_required,
    creator_only_required, creator_required,
)
from utils.helpers import *
from utils.constants import *
from utils.security import get_session_token, has_access, has_video_access, has_post_access
from utils.validators import allowed_file, allowed_video, allowed_image, allowed_video_file
from utils.formatter import dynamic_price, get_current_price, make_slug, _time_ago
from services.email_service import (
    send_welcome_email, send_account_grant_email, send_application_notification_email,
)
from services.payment_service import create_binance_signature
from services.wallet_service import (
    get_revenue_split, split_revenue, get_user_balances, get_user_revenue_breakdown,
    lock_earnings_for_withdrawal, release_locked_earnings, check_graduation,
    is_withdrawal_day, next_withdrawal_day, make_transaction_ref,
    junior_creator_sales_count, junior_creator_is_eligible_for_promotion,
)
from services.upload_service import generate_watermark_preview, get_blur_settings, check_upload_allowed
from services.notification_service import (
    recalculate_engagement, log_activity, push_notification,
    notify_followers, broadcast_notification,
)
from services.analytics_service import *
from services.creator_service import resolve_creator_dashboard_profile, upload_url, is_admin_override
from services.auth_service import get_setting, set_setting
from config import Config
import stripe as stripe_module

payment_bp = Blueprint("payment", __name__)

@payment_bp.route('/checkout/<int:photo_id>', endpoint='checkout')
    
def checkout(photo_id):
    # Try photo first, then video
    content_type = 'photo'
    photo = db.session.get(Photo, photo_id)
    if not photo:
        # It's a video
        video = Video.query.get(photo_id)
        if not video:
            abort(404)
        # Build a pseudo-photo object for the template
        class _VideoProxy:
            pass
        photo = _VideoProxy()
        photo.id = video.id
        photo.title = video.title
        photo.description = video.description or ''
        photo.tier = video.tier
        photo.unlock_price = video.unlock_price
        photo.unlock_duration = video.unlock_duration
        photo.current_price = video.unlock_price
        photo.preview_filename = video.thumbnail_filename
        content_type = 'video'
    else:
        photo.current_price = dynamic_price(photo)

    tok = get_session_token()
    user_name = "Guest"
    user_email = "guest@example.com"
    if session.get('user_id'):
        user = User.query.get(session['user_id'])
        if user:
            user_email = user.email
            user_name = user.email.split('@')[0]

    return render_template(
        'checkout.html',
        photo=photo,
        session_token=tok,
        stripe_pk=STRIPE_PUBLISHABLE_KEY,
        user_name=user_name,
        user_email=user_email,
        content_type=content_type
    )




@payment_bp.route('/payments/stripe/create-session', methods=['POST'], endpoint='stripe_create_session')
    
def stripe_create_session():
    try:
        data = request.get_json()

        # Current browser session token
        tok = get_session_token()

        # Request data
        photo_id = data.get("photo_id")
        user_name = data.get("customer_name")
        user_email = data.get("customer_email")

        # Validation
        if not photo_id:
            return jsonify({
                "error": "photo_id is required"
            }), 400

        if not user_name or not user_email:
            return jsonify({
                "error": "Customer details required"
            }), 400

        # Get photo
        photo = Photo.query.get_or_404(photo_id)
        price = dynamic_price(photo)

        # Create order
        order = Order(
            order_id=str(uuid.uuid4()),
            customer_name=user_name,
            customer_email=user_email,
            total_price=price,
            total_items=1
        )

        db.session.add(order)
        db.session.flush()

        # Create order item
        item = OrderItem(
            order_id=order.id,
            product_id=photo.id,
            product_name=photo.title,
            quantity=1,
            unit_price=price,
            total_price=price
        )

        db.session.add(item)
        db.session.commit()

        # Create Stripe Checkout Session
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],

            line_items=[{
                'price_data': {
                    'currency': 'usd',

                    'product_data': {
                        'name': photo.title,
                        'description': "{} tier access".format(photo.tier)
                    },

                    'unit_amount': int(price * 100),
                },

                'quantity': 1,
            }],

            mode='payment',

            success_url=url_for(
                'payment_success',
                _external=True
            ) + "?order_id={}&photo_id={}".format(
                order.order_id,
                photo_id
            ),

            cancel_url=url_for(
                'photo_detail',
                photo_id=photo_id,
                _external=True
            ),

            metadata={
                "order_id": order.order_id,
                "photo_id": str(photo_id),
                "customer_email": user_email,
                "session_token": tok
            }
        )

        return jsonify({
            'url': checkout_session.url
        })

    except Exception as e:
        print("🔥 ERROR:", str(e))

        return jsonify({
            'error': str(e)
        }), 500




@payment_bp.route('/payments/stripe/webhook', methods=['POST'], endpoint='stripe_webhook')
    
def stripe_webhook():
    print("🔥 STRIPE WEBHOOK HIT")

    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')

    try:
        event = stripe.Webhook.construct_event(
            payload,
            sig_header,
            STRIPE_WEBHOOK_SECRET
        )

        print("✅ Event verified:", event['type'])

    except ValueError:
        print("❌ Invalid payload")
        return 'Invalid payload', 400

    except stripe.error.SignatureVerificationError:
        print("❌ Invalid signature")
        return 'Invalid signature', 400

    # Only handle successful checkout
    if event['type'] != 'checkout.session.completed':
        print("⚠️ Ignored event:", event['type'])
        return '', 200

    try:
        session_data = event['data']['object']

        metadata = session_data.get('metadata', {})

        # ── VaultX: DM-unlock completions ────────────────────────────────
        # These use a separate metadata schema (vaultx_type/vault_ref) from
        # the photo/video Order flow below, so handle them first and return.
        if metadata.get('vaultx_type') == 'dm_unlock':
            vault_ref = metadata.get('vault_ref')
            tx = VaultTransaction.query.filter_by(reference=vault_ref).first()
            if not tx:
                print('❌ VaultX dm_unlock: transaction reference not found:', vault_ref)
                return '', 200
            if tx.status == 'completed':
                print('⚠️ VaultX dm_unlock already processed:', vault_ref)
                return '', 200
            msg_row = DMMessage.query.get(tx.content_id)
            if not msg_row:
                print('❌ VaultX dm_unlock: message not found for tx', vault_ref)
                return '', 200
            tx.status = 'completed'
            db.session.flush()
            split_revenue(tx)
            msg_row.is_unlocked = True
            db.session.commit()
            print('✅ VaultX dm_unlock completed:', vault_ref)
            return '', 200

        order_uuid = metadata.get('order_id')
        photo_id = metadata.get('photo_id')
        customer_email = metadata.get('customer_email')
        session_token = metadata.get('session_token')

        payment_intent = session_data.get('payment_intent')

        print("📦 ORDER UUID:", order_uuid)

        if not order_uuid:
            print("❌ Missing order_id")
            return '', 200

        # =========================================
        # FIND ORDER
        # =========================================
        order = Order.query.filter_by(
            order_id=order_uuid
        ).first()

        if not order:
            print("❌ Order not found")
            return '', 200

        # Prevent duplicate processing
        existing_payment = Payment.query.filter_by(
            transaction_id=payment_intent
        ).first()

        if existing_payment and existing_payment.status == 'completed':
            print("⚠️ Payment already processed")
            return '', 200

        # =========================================
        # UPDATE ORDER STATUS
        # =========================================
        order.delivery_status = 'successful'

        # =========================================
        # GET ORDER ITEMS
        # =========================================
        order_items = OrderItem.query.filter_by(
            order_id=order.id
        ).all()

        if not order_items:
            print("❌ No order items found")
            return '', 200

        # =========================================
        # CREATE PURCHASE + PAYMENT RECORDS
        # =========================================
        email_images = []

        for item in order_items:

            photo = Photo.query.get(item.product_id)

            if not photo:
                continue

            # Save purchase
            purchase = Purchase(
                session_token=session_token,
                photo_id=photo.id,
                payment_method='stripe',
                amount=item.total_price,
                expires_at=datetime.utcnow() + timedelta(
                    hours=photo.unlock_duration
                ),
                is_permanent=False
            )

            db.session.add(purchase)

            # Save payment
            payment = Payment(
                session_token=session_token,
                gateway='stripe',
                transaction_id=payment_intent,
                amount=item.total_price,
                status='completed',
                photo_id=photo.id
            )

            db.session.add(payment)

            # Store image path for email
            image_path = os.path.join(
                current_app.config['UPLOAD_FOLDER'],
                photo.original_filename
            )

            if os.path.exists(image_path):
                email_images.append({
                    "title": photo.title,
                    "path": image_path,
                    "filename": photo.original_filename
                })

    # Commit DB changes
        db.session.commit()

        print("✅ Order updated successfully")

        # =========================================
        # SEND EMAIL WITH IMAGES
        # =========================================

        try:

            msg = Message(
                subject="Your PhotoVault Purchase",
                sender=current_app.config['MAIL_USERNAME'],
                recipients=[order.customer_email]
            )

            premium_link = "https://mitchellkaori.top/premiums?order_id={}".format(
                order.order_id
            )

            msg.html = """
            <h2>Thank You For Your Purchase</h2>

            <p>Hello {}</p>

            <p>Your payment was successful.</p>

            <p>Your purchased images are ready.</p>

            <p>
                <strong>Order ID:</strong> {}
            </p>

            <p>
                <a href="{}">
                    Click Here To Download Your Images
                </a>
            </p>
            """.format(
                order.customer_name,
                order.order_id,
                premium_link
            )

            for img in email_images:

                with current_app.open_resource(img["path"]) as fp:

                    msg.attach(
                        img["filename"],
                        "image/jpeg",
                        fp.read()
                    )

            mail.send(msg)

            print("📧 Email sent successfully")

        except Exception as email_error:

            print("❌ Email sending failed:", str(email_error))

        return '', 200
        
        
    except Exception as e:
        db.session.rollback()

        print("🔥 WEBHOOK ERROR:", str(e))

        return 'Webhook error', 500



@payment_bp.route('/checkout/paystack/paymentsuccessful', endpoint='payment_successful_paystack')
    
def payment_successful_paystack():

    return render_template(
        'payment_successful.html'
    )
    


@payment_bp.route('/payments/paystack/initialize', methods=['POST'], endpoint='paystack_initialize')
    
def paystack_initialize():
    try:
        data = request.get_json()

        # Current browser session token
        tok = get_session_token()

        # Request data
        photo_id = data.get("photo_id")
        user_name = data.get("customer_name")
        user_email = data.get("customer_email")

        # Validation
        if not photo_id:
            return jsonify({
                "error": "photo_id is required"
            }), 400

        if not user_name or not user_email:
            return jsonify({
                "error": "Customer details required"
            }), 400

        # Get photo
        photo = Photo.query.get_or_404(photo_id)

        # Dynamic pricing
        price = dynamic_price(photo)

        # =========================
        # CREATE ORDER
        # =========================
        order = Order(
            order_id=str(uuid.uuid4()),
            customer_name=user_name,
            customer_email=user_email,
            total_price=price,
            total_items=1
        )

        db.session.add(order)
        db.session.flush()

        # =========================
        # CREATE ORDER ITEM
        # =========================
        item = OrderItem(
            order_id=order.id,
            product_id=photo.id,
            product_name=photo.title,
            quantity=1,
            unit_price=price,
            total_price=price
        )

        db.session.add(item)
        db.session.commit()

        # =========================
        # PAYSTACK AMOUNT
        # Paystack expects smallest currency unit
        # KES -> cents
        # NGN -> kobo
        # USD -> cents
        # =========================
        paystack_amount = int(float(price) * 100)

        # =========================
        # CALLBACK URL
        # =========================
        callback_url = "https://mitchellkaori.top/checkout/paystack/paymentsuccessful"

        # =========================
        # PAYSTACK PAYLOAD
        # =========================
        payload = {
            "email": user_email,
            "amount": paystack_amount,
            "currency": "USD",

            # Unique transaction reference
            "reference": order.order_id,
            

            "callback_url": callback_url,

            "metadata": {
                "order_id": order.order_id,
                "photo_id": str(photo.id),
                "customer_email": user_email,
                "customer_name": user_name,
                "session_token": tok
            }
        }

        headers = {
            "Authorization": "Bearer {}".format(
                PAYSTACK_SECRET_KEY
            ),
            "Content-Type": "application/json"
        }

        # =========================
        # INITIALIZE PAYMENT
        # =========================
        response = requests.post(
            PAYSTACK_INITIALIZE_URL,
            json=payload,
            headers=headers
        )

        response_data = response.json()

        print("PAYSTACK RESPONSE:", response_data)

        # =========================
        # ERROR CHECKING
        # =========================
        if not response_data.get("status"):
            return jsonify({
                "error": response_data.get("message", "Paystack initialization failed")
            }), 400

        # =========================
        # AUTHORIZATION URL
        # =========================
        authorization_url = response_data["data"]["authorization_url"]

        return jsonify({
            "status": True,
            "message": "Payment initialized successfully",
            "payment": "paystack",
            "url": authorization_url,
            "reference": order.order_id
        })

    except Exception as e:
        print("🔥 PAYSTACK ERROR:", str(e))

        db.session.rollback()

        return jsonify({
            "error": str(e)
        }), 500

    

@payment_bp.route('/test-email', endpoint='test_email')
    
def test_email():

    try:

        msg = Message(

            subject='TEST EMAIL',

            sender=(
                'PhotoVault',
                current_app.config['MAIL_USERNAME']
            ),

            recipients=['@gmail.com']
        )

        msg.body = 'Email test successful'

        mail.send(msg)

        return 'EMAIL SENT'

    except Exception as e:

        traceback.print_exc()

        return str(e)



@payment_bp.route('/payments/paystack/verify/<reference>', methods=['GET'], endpoint='verify_paystack_payment')
    
def verify_paystack_payment(reference):

    try:

        # =========================
        # VERIFY WITH PAYSTACK
        # =========================
        verify_url = (
            "https://api.paystack.co/transaction/verify/{}"
        ).format(reference)

        headers = {
            "Authorization": "Bearer {}".format(
                PAYSTACK_SECRET_KEY
            ),
        }

        response = requests.get(
            verify_url,
            headers=headers
        )

        response_data = response.json()

        print("PAYSTACK VERIFY RESPONSE:", response_data)

        # =========================
        # VERIFY RESPONSE STATUS
        # =========================
        if not response_data.get("status"):

            return jsonify({
                "error": "Unable to verify payment"
            }), 400

        payment_data = response_data.get("data")

        # =========================
        # PAYMENT MUST BE SUCCESS
        # =========================
        if payment_data.get("status") != "success":

            return jsonify({
                "error": "Payment not successful"
            }), 400

        # =========================
        # GET METADATA
        # =========================
        metadata = payment_data.get("metadata", {})

        order_id = metadata.get("order_id")
        photo_id = metadata.get("photo_id")
        customer_email = metadata.get("customer_email")
        session_token = metadata.get("session_token")

        # =========================
        # VALIDATION
        # =========================
        if not order_id or not photo_id:

            return jsonify({
                "error": "Invalid payment metadata"
            }), 400

        # =========================
        # FIND ORDER
        # =========================
        order = Order.query.filter_by(
            order_id=order_id
        ).first()

        if not order:

            return jsonify({
                "error": "Order not found"
            }), 404

        # =========================
        # PREVENT DUPLICATES
        # =========================
        existing_purchase = Purchase.query.filter_by(
            session_token=session_token
        ).first()

        if existing_purchase:

            print("Purchase already exists")

            return redirect(
                url_for(
                    'photo_detail',
                    photo_id=photo_id
                )
            )

        # =========================
        # GET PHOTO
        # =========================
        photo = db.session.get(Photo, photo_id)

        if not photo:

            return jsonify({
                "error": "Photo not found"
            }), 404

        # =========================
        # ACCESS EXPIRY
        # =========================
        expires_at = datetime.utcnow() + timedelta(
            hours=photo.unlock_duration
        )

        # =========================
        # CREATE PURCHASE
        # =========================
        purchase = Purchase(

            session_token=session_token,

            user_id=None,

            photo_id=photo.id,

            payment_method="paystack",

            amount=payment_data.get("amount", 0) / 100,

            expires_at=expires_at,

            is_permanent=False,

            created_at=datetime.utcnow()
        )

        db.session.add(purchase)

        # =========================
        # UPDATE ORDER STATUS
        # =========================
        order.delivery_status = "completed"

        # =========================
        # INCREMENT DOWNLOADS
        # =========================
        order.downloads = (order.downloads or 0) + 1

        # =========================
        # OPTIONAL:
        # INCREMENT VIEW COUNT
        # =========================
        photo.view_count = (photo.view_count or 0) + 1

        # =========================
        # SAVE
        # =========================
        db.session.commit()



        # =========================
        # REDIRECT USER
        # =========================
        return redirect(
            url_for(
                'photo_detail',
                photo_id=photo.id,
                payment="success"
            )
        )

    except Exception as e:

        print("🔥 PAYSTACK VERIFY ERROR:", str(e))

        db.session.rollback()

        return jsonify({
            "error": str(e)
        }), 500




@payment_bp.route('/payments/paystack/webhook', methods=['POST'], endpoint='paystack_webhook')
    
def paystack_webhook():
    print("🔥 PAYSTACK WEBHOOK HIT")

    try:
        # =====================================
        # RAW PAYLOAD & SIGNATURE VERIFICATION
        # =====================================
        payload = request.data
        if not payload:
            print("❌ EMPTY PAYLOAD")
            return '', 400

        paystack_signature = request.headers.get('x-paystack-signature')
        computed_signature = hmac.new(
            PAYSTACK_SECRET_KEY.encode('utf-8'),
            payload,
            hashlib.sha512
        ).hexdigest()

        if paystack_signature != computed_signature:
            print("❌ INVALID SIGNATURE")
            return 'Invalid signature', 400

        print("✅ SIGNATURE VERIFIED")

        # =====================================
        # PARSE INCOMING EVENT
        # =====================================
        event = request.get_json()
        if not event:
            print("❌ INVALID JSON")
            return '', 400

        event_type = event.get('event')
        print("✅ EVENT:", event_type)

        if event_type != 'charge.success':
            print("⚠️ EVENT IGNORED:", event_type)
            return '', 200

        # =====================================
        # LOCAL DATA EXTRACTION
        # =====================================
        payment_data = event.get('data', {}) or {}
        metadata = payment_data.get('metadata', {}) or {}

        order_uuid = metadata.get('order_id')
        session_token = metadata.get('session_token')
        transaction_reference = payment_data.get('reference')
        total_amount = payment_data.get('amount', 0) / 100.0

        print("📦 ORDER UUID FROM PAYSTACK METADATA: {}".format(order_uuid))

        if not order_uuid:
            print("❌ Missing order_id inside payload metadata")
            return '', 200

        # =========================================
        # FIND AND VERIFY ORDER (Following Stripe approach)
        # =========================================
        order = Order.query.filter_by(order_id=order_uuid).first()
        if not order:
            print("❌ Order not found in database for UUID: {}".format(order_uuid))
            return '', 200

        # Save recipient details out immediately before session modification
        recipient_email = order.customer_email
        recipient_name = order.customer_name or "Valued Customer"

        # Prevent duplicate fulfillment handling
        existing_payment = Payment.query.filter_by(transaction_id=transaction_reference).first()
        if existing_payment and existing_payment.status == 'completed':
            print("⚠️ Payment reference already successfully processed")
            return '', 200

        # =========================================
        # UPDATE ORDERS & RELATED ENTITIES
        # =========================================
        # Directly updates 'delivery_status' inside 'public.orders' table
        order.delivery_status = 'successful'
        if order.downloads is None:
            order.downloads = 0

        # Fetch matching items purchased under this order context
        order_items = OrderItem.query.filter_by(order_id=order.id).all()
        if not order_items:
            print("❌ No order items linked to order ID: {}".format(order.id))
            return '', 200

        # Loop items to create unlock accesses & logs (matches your Stripe pattern)
        for item in order_items:
            photo = Photo.query.get(item.product_id)
            if not photo:
                continue

            # Provision purchase download right allowances
            existing_purchase = Purchase.query.filter_by(
                session_token=session_token,
                photo_id=photo.id
            ).first()

            if not existing_purchase:
                purchase = Purchase(
                    session_token=session_token,
                    photo_id=photo.id,
                    payment_method='paystack',
                    amount=item.total_price,
                    expires_at=datetime.utcnow() + timedelta(hours=photo.unlock_duration),
                    is_permanent=False
                )
                db.session.add(purchase)

            # Record audit logs for payment tracking
            payment = Payment(
                order_id=order.id,
                session_token=session_token,
                gateway='paystack',
                transaction_id=transaction_reference,
                amount=item.total_price,
                status='completed',
                photo_id=photo.id
            )
            db.session.add(payment)

        # =========================================
        # COMMIT TRANSACTION TO DATABASE
        # =========================================
        db.session.commit()
        print("✅ ORDERS AND PURCHASES TABLES SUCCESSFULLY REFRESHED ON DISK")

        # =========================================
        # TEXT-ONLY OUTBOUND EMAIL ROUTING ZONE
        # =========================================
        if not recipient_email:
            print("❌ Cancelled mail routing: Destination email field is empty.")
            return '', 200

        try:
            msg = Message(
                subject="Your PhotoVault Purchase",
                sender=current_app.config['MAIL_DEFAULT_SENDER'],
                recipients=[recipient_email]
            )

            premium_link = "https://mitchellkaori.top/premiums?order_id={}".format(order_uuid)

            msg.html = """
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #eeeeee;">
                <h2 style="color: #333333;">Thank You For Your Purchase</h2>
                <p>Hello {},</p>
                <p>Your payment via Paystack was processed successfully.</p>
                <p>Your purchased images are now unlocked and available for download.</p>
                
                <div style="background-color: #f9f9f9; padding: 15px; border-radius: 5px; margin: 20px 0;">
                    <p style="margin: 5px 0;"><strong>Order ID:</strong> {}</p>
                    <p style="margin: 5px 0;"><strong>Transaction Ref:</strong> {}</p>
                </div>
                
                <p style="margin-top: 30px; margin-bottom: 30px;">
                    <a href="{}" style="padding: 12px 25px; background-color: #007bff; color: #ffffff; text-decoration: none; border-radius: 5px; font-weight: bold; display: inline-block;">Click Here To Download Your Images</a>
                </p>
                <p style="color: #777777; font-size: 12px;">If the button above does not work, copy and paste this link into your browser:<br>{}</p>
            </div>
            """.format(
                recipient_name,
                order_uuid,
                transaction_reference,
                premium_link,
                premium_link
            )

            print("📧 Dispatching text email route to: {}...".format(recipient_email))
            mail.send(msg)
            print("📧 Email delivered successfully.")

        except Exception as email_send_error:
            print("❌ Outbound mail generation dropped: {}".format(str(email_send_error)))

        return '', 200

    except Exception as general_error:
        db.session.rollback()
        print("🔥 CRITICAL RUNTIME SYSTEM WEBHOOK ERROR: {}".format(str(general_error)))
        return 'Webhook handling failure', 500
    finally:
        # Prevent thread session leakage or locking across previews
        db.session.remove()

        
# ============================================
# PAYSTACK WEBHOOK ABOVE
# ============================================


@payment_bp.route('/checkout/paymentsuccessful', endpoint='payment_successful')
    
def payment_successful():

    return """
    <!DOCTYPE html>
    <html>

    <head>

        <title>
            Payment Successful
        </title>

        <style>

            body{

                margin:0;
                padding:0;
                background:#f5f5f5;
                font-family:Arial;
            }

            .box{

                width:90%;
                max-width:600px;

                background:white;

                margin:80px auto;

                padding:40px;

                border-radius:10px;

                text-align:center;

                box-shadow:0 0 20px rgba(0,0,0,0.1);
            }

            h1{

                color:green;
            }

            p{

                color:#555;
                line-height:1.8;
            }

            a{

                display:inline-block;

                margin-top:20px;

                padding:12px 25px;

                background:black;

                color:white;

                text-decoration:none;

                border-radius:6px;
            }

        </style>

    </head>

    <body>

        <div class="box">

            <h1>
                Payment Successful
            </h1>

            <p>
                Your payment has been received successfully.
            </p>

            <p>
                Please check your email for your order details
                and premium access link.
            </p>

            <a href="/">
                Go Back Home
            </a>

        </div>

    </body>

    </html>
    """


@payment_bp.route('/payments/binance/create', methods=['POST'], endpoint='binance_create')
    
def binance_create():
    data     = request.get_json()
    photo_id = data.get('photo_id')
    tok      = get_session_token()
    photo    = Photo.query.get_or_404(photo_id)
    price    = dynamic_price(photo)

    nonce     = uuid.uuid4().hex[:32]
    timestamp = str(int(time.time() * 1000))

    body_dict = {"env": {"terminalType": "WEB"}, "merchantTradeNo": nonce,
                 "orderAmount": str(price), "currency": "USDT",
                 "goods": {"goodsType": "01", "goodsCategory": "D000",
                            "goodsName": photo.title, "referenceGoodsId": str(photo_id)},
                 "returnUrl": url_for('payment_success', _external=True) + '?photo_id={}&session_token={}'.format(photo_id, tok),
                 "cancelUrl": url_for('photo_detail', photo_id=photo_id, _external=True)}

    body      = json.dumps(body_dict)
    signature = create_binance_signature(timestamp, nonce, body)

    headers = {"Content-Type": "application/json", "BinancePay-Timestamp": timestamp,
               "BinancePay-Nonce": nonce, "BinancePay-Certificate-SN": BINANCE_API_KEY,
               "BinancePay-Signature": signature}

    try:
        response = requests.post("{}/binancepay/openapi/v2/order".format(BINANCE_BASE_URL), headers=headers, data=body)
        resp = response.json()
        if resp.get("status") == "SUCCESS":
            checkout_url = resp["data"]["checkoutUrl"]
            payment = Payment(session_token=tok, gateway="binance", transaction_id=nonce,
                              amount=price, status="pending", photo_id=photo_id)
            db.session.add(payment)
            db.session.commit()
            return jsonify({"url": checkout_url})
        return jsonify({"error": resp.get("errorMessage", "Binance error")}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500



@payment_bp.route('/payments/binance/webhook', methods=['POST'], endpoint='binance_webhook')
    
def binance_webhook():
    data = request.get_json()
    if data.get("bizStatus") != "PAY_SUCCESS":
        return jsonify({"returnCode": "SUCCESS"}), 200
    try:
        biz_content      = json.loads(data.get("bizContent", "{}"))
        merchant_trade_no = biz_content.get("merchantTradeNo")
        payment = Payment.query.filter_by(transaction_id=merchant_trade_no).first()
        if not payment or payment.status == "completed":
            return jsonify({"returnCode": "SUCCESS"}), 200
        photo = Photo.query.get(payment.photo_id)
        if not photo:
            return jsonify({"returnCode": "FAIL"}), 400
        purchase = Purchase(session_token=payment.session_token, photo_id=photo.id,
                            payment_method="binance", amount=payment.amount,
                            expires_at=datetime.utcnow() + timedelta(hours=photo.unlock_duration),
                            is_permanent=False)
        db.session.add(purchase)
        payment.status = "completed"
        db.session.commit()
        return jsonify({"returnCode": "SUCCESS"}), 200
    except Exception as e:
        print("Binance webhook error:", e)
        return jsonify({"returnCode": "FAIL"}), 400



@payment_bp.route('/payment/success', endpoint='payment_success')
    
def payment_success():
    photo_id   = request.args.get('photo_id', type=int)
    order_uuid = request.args.get('order_id')
    reference  = request.args.get('reference')
    photo      = db.session.get(Photo, photo_id) if photo_id else None
    has_paid   = False
    download_link = None

    if photo and order_uuid:
        try:
            order = Order.query.filter_by(order_id=order_uuid).first()
            if reference and order:
                headers       = {"Authorization": "Bearer {}".format(PAYSTACK_SECRET_KEY)}
                response      = requests.get("https://api.paystack.co/transaction/verify/{}".format(reference), headers=headers)
                response_data = response.json()
                if response_data.get("status") and response_data["data"]["status"] == "success":
                    if order.delivery_status != "successful":
                        metadata      = response_data["data"].get("metadata", {})
                        session_token = metadata.get("session_token")
                        existing      = Purchase.query.filter_by(session_token=session_token).first()
                        if not existing:
                            purchase = Purchase(session_token=session_token, user_id=None, photo_id=photo.id,
                                                payment_method="paystack",
                                                amount=response_data["data"]["amount"] / 100,
                                                expires_at=datetime.utcnow() + timedelta(hours=photo.unlock_duration),
                                                is_permanent=False, created_at=datetime.utcnow())
                            db.session.add(purchase)
                        order.delivery_status = "successful"
                        photo.downloads       = (photo.downloads or 0) + 1
                        photo.view_count      = (photo.view_count or 0) + 1
                        db.session.commit()
            if order and order.delivery_status == 'successful':
                has_paid = True
                download_link = url_for('download_photo', order_uuid=order.order_id, photo_id=photo.id, _external=True)
        except Exception as e:
            db.session.rollback()
            print("Payment success error:", str(e))

    return render_template('payment_success.html', photo=photo, has_paid=has_paid, download_link=download_link)



@payment_bp.route('/premiums', methods=['GET', 'POST'], endpoint='premiums')
    
def premiums():

    photos = []
    order = None
    error = None

    order_uuid = None

    # =========================================
    # GET METHOD
    # /premiums?order_id=XXXX
    # =========================================

    if request.method == 'GET':

        order_uuid = request.args.get('order_id')

    # =========================================
    # POST METHOD
    # FORM SUBMISSION
    # =========================================

    elif request.method == 'POST':

        order_uuid = request.form.get('order_id')

    # =========================================
    # PROCESS ORDER
    # =========================================

    if order_uuid:

        order = Order.query.filter_by(
            order_id=order_uuid
        ).first()

        if not order:

            error = "Invalid Order ID"

        elif order.delivery_status != 'successful':

            error = "Payment not completed yet"

        else:

            order_items = OrderItem.query.filter_by(
                order_id=order.id
            ).all()

            for item in order_items:

                photo = Photo.query.get(item.product_id)

                if photo:

                    photos.append(photo)

    return render_template(
        'premiums.html',
        photos=photos,
        order=order,
        error=error
    )



@payment_bp.route('/download/<order_uuid>/<int:photo_id>', endpoint='download_photo')
    
def download_photo(order_uuid, photo_id):
    order = Order.query.filter_by(order_id=order_uuid).first()
    if not order:
        abort(403)
    if order.delivery_status != 'successful':
        return "Payment not completed"
    if order.downloads is None:
        order.downloads = 0
    if int(order.downloads) >= 1:
        return "Already downloaded"
    order_item = OrderItem.query.filter_by(order_id=order.id, product_id=photo_id).first()
    if not order_item:
        abort(403)
    photo = db.session.get(Photo, photo_id)
    if not photo:
        abort(404)
    originals_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'originals')
    file_path     = os.path.join(originals_dir, photo.original_filename)
    if not os.path.exists(file_path):
        abort(404)
    order.downloads = int(order.downloads) + 1
    db.session.commit()
    return send_from_directory(originals_dir, photo.original_filename, as_attachment=True)



@payment_bp.route('/photo-original/<filename>', endpoint='photo_original')
    
def photo_original(filename):
    originals_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'originals')
    return send_from_directory(originals_dir, filename)



@payment_bp.route('/charge', methods=['POST'], endpoint='charge')
    
def charge():
    return jsonify({"status": "success"}), 200

