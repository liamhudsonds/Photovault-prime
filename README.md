# ⬡ PhotoVault — Premium Photo Access Platform

A full-stack Flask web application for selling timed access to premium photos. Users can browse, pay (via Stripe or Binance Pay), and unlock high-resolution images — **no account required**.

---

## 🗂 Project Structure

```
photovault/
├── app.py                  # Main Flask application (backend + routes)
├── requirements.txt        # Python dependencies
├── .env.example            # Environment variables template
├── .env                    # Your actual secrets (not committed to git)
├── uploads/
│   ├── originals/          # Original full-res images (protected)
│   └── previews/           # Auto-generated watermarked previews
├── static/
│   ├── css/style.css       # All styles
│   └── js/main.js          # Frontend JS
└── templates/
    ├── base.html           # Shared nav/footer layout
    ├── index.html          # Homepage
    ├── gallery.html        # Photo gallery with filters
    ├── photo_detail.html   # Single photo page
    ├── checkout.html       # Payment selection
    ├── payment_success.html
    ├── login.html
    ├── register.html
    ├── admin_login.html
    ├── admin_dashboard.html
    ├── admin_upload.html
    ├── admin_edit_photo.html
    └── admin_revenue.html
```

---

## ⚙️ Setup Instructions

### 1. Prerequisites

- Python 3.10 or higher
- pip

### 2. Clone / Download

```bash
cd photovault
```

### 3. Create a virtual environment

```bash
python -m venv venv
source venv/bin/activate        # macOS/Linux
venv\Scripts\activate           # Windows
```

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

### 5. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and fill in:
- `SECRET_KEY` — any long random string
- `STRIPE_SECRET_KEY` / `STRIPE_PUBLISHABLE_KEY` — from [Stripe Dashboard](https://dashboard.stripe.com/apikeys)
- `STRIPE_WEBHOOK_SECRET` — from your Stripe webhook endpoint settings
- `BINANCE_API_KEY` / `BINANCE_SECRET_KEY` — from [Binance Merchant](https://merchant.binance.com/en/developer/config)
- `ADMIN_EMAIL` / `ADMIN_PASSWORD` — your desired admin credentials

Binance Secrete key : LVnqayReuN4W77s8VBE9YSf7HKAo2YLFqzxT4dQASxc23zNAmGD3LWDf7gn93cz4
binace Api:p8Yo20DROS00vwLUFrEsA9W4giLnYWkJm2LLmDcUtTvx9sljPYSjsyUUTF7oKGSM

To load the `.env` file, install python-dotenv and add at the top of `app.py` if not there:
```python
from dotenv import load_dotenv
load_dotenv()
```

### 6. Run the application

```bash
python app.py
```

The app starts on **http://localhost:5000**

On first run:
- The SQLite database (`photovault.db`) is created automatically
- The admin account is created with your `ADMIN_EMAIL` / `ADMIN_PASSWORD`

---

## 🔑 Admin Panel

Visit: **http://localhost:5000/admin/login**

Default credentials (change in `.env`):
- Email: `admin@photovault.com`
- Password: `Admin@1234`

### Admin can:
- Upload photos (watermarked preview auto-generated)
- Set tier (Basic / Advanced / Premium), price, access duration
- Enable dynamic pricing
- View all users and block/unblock them
- View all revenue and transactions
- Edit or deactivate photos

---

## 💳 Payment Flow

### Stripe (Card / Apple Pay / Google Pay)
1. User clicks "Unlock Now" → hits `/payments/stripe/create-session`
2. Flask creates a Stripe Checkout session
3. User is **redirected to Stripe's hosted payment page**
4. After payment, Stripe redirects back to `/payment/success`
5. Stripe also fires a webhook to `/payments/stripe/webhook`
6. Backend grants access to the photo for the configured duration

### Binance Pay (Crypto: USDT / BTC / ETH / BNB)
1. User clicks "Pay with Crypto" → hits `/payments/binance/create`
2. Flask calls Binance Pay API and gets a checkout URL
3. User is **redirected to Binance Pay's hosted page**
4. After payment, Binance redirects back and fires webhook to `/payments/binance/webhook`
5. Backend grants access

---

## 🔒 Security Notes

- Original images are **never exposed publicly** — served only via `/img/original/<id>` with access check
- All previews are watermarked server-side using Pillow
- Payment webhooks verified with signatures
- Session tokens stored in browser cookies to track access
- Rate limiting can be added via `flask-limiter` (not included by default)

---

## 🌐 Setting Up Stripe Webhooks

1. Install [Stripe CLI](https://stripe.com/docs/stripe-cli)
2. For local development:
   ```bash
   stripe listen --forward-to localhost:5000/payments/stripe/webhook
   ```
3. Copy the displayed webhook secret to `STRIPE_WEBHOOK_SECRET` in `.env`
4. For production, set up the webhook in Stripe Dashboard → Developers → Webhooks
   - URL: `https://yourdomain.com/payments/stripe/webhook`
   - Event: `checkout.session.completed`

---

## 🚀 Production Deployment

### With Gunicorn + Nginx

```bash
# Start with Gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

### Switch to PostgreSQL
```
DATABASE_URL=postgresql://user:password@localhost:5432/photovault
```
Install: `pip install psycopg2-binary`

### Use cloud storage (AWS S3 / Cloudflare R2)
For production, replace local file serving with signed URLs from S3/R2. The `UPLOAD_FOLDER` paths in `app.py` are the integration points.

---

## 📦 Tech Stack

| Layer      | Technology                       |
|------------|----------------------------------|
| Backend    | Flask (Python)                   |
| Database   | SQLite (dev) / PostgreSQL (prod) |
| ORM        | Flask-SQLAlchemy                 |
| Auth       | Flask sessions + Bcrypt          |
| Payments   | Stripe API + Binance Pay API     |
| Images     | Pillow (watermarking)            |
| Frontend   | HTML + CSS + Vanilla JS          |
| Fonts      | Playfair Display + DM Sans       |
| Deployment | Gunicorn + Nginx                 |

---

## 🎨 Design

Dark luxury aesthetic with gold accents, grain texture overlay, and smooth fade-up animations. Mobile responsive.

---

## 📋 Database Schema

| Table     | Key Fields                                                        |
|-----------|-------------------------------------------------------------------|
| users     | id, email, password_hash, is_admin, is_blocked                    |
| photos    | id, title, tier, preview_filename, original_filename, unlock_price, unlock_duration |
| purchases | id, session_token, photo_id, payment_method, expires_at           |
| payments  | id, session_token, gateway, transaction_id, amount, status        |

---

## 🔧 Customization

- **Add tiers**: Update the `tier` field choices in `Photo` model and CSS classes in `style.css`
- **Change access duration**: Default is set per-photo in the admin upload form
- **Dynamic pricing**: Enable per-photo in admin; price bumps by $0.50 per 10 views
- **Email notifications**: Configure Flask-Mail in `app.py` with your SMTP settings

---

*Built with Flask · Stripe · Binance Pay · SQLAlchemy · Pillow*
