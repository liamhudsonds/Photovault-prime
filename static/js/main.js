// ── Intersection observer for fade-up animations ──────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.style.opacity = '1';
        entry.target.style.transform = 'translateY(0)';
      }
    });
  }, { threshold: 0.1, rootMargin: '0px 0px -40px 0px' });

  document.querySelectorAll('.fade-up').forEach(el => {
    el.style.opacity = '0';
    el.style.transform = 'translateY(24px)';
    el.style.transition = 'opacity .5s ease, transform .5s ease';
    observer.observe(el);
  });

  // ── Tier pills on gallery ─────────────────────────────────────────────────
  document.querySelectorAll('.tier-pill').forEach(pill => {
    pill.addEventListener('click', (e) => {
      // navigation handled by href; just add active class immediately for feel
      document.querySelectorAll('.tier-pill').forEach(p => p.classList.remove('active'));
      pill.classList.add('active');
    });
  });

  // ── Upload zone drag-and-drop ─────────────────────────────────────────────
  const zone = document.getElementById('upload-zone');
  if (zone) {
    zone.addEventListener('dragover', (e) => {
      e.preventDefault();
      zone.style.borderColor = 'var(--gold)';
      zone.style.background = 'var(--gold-dim)';
    });
    zone.addEventListener('dragleave', () => {
      zone.style.borderColor = 'var(--border)';
      zone.style.background = 'transparent';
    });
    zone.addEventListener('drop', (e) => {
      e.preventDefault();
      zone.style.borderColor = 'var(--border)';
      zone.style.background = 'transparent';
      const input = document.getElementById('photo-input');
      if (input && e.dataTransfer.files.length) {
        input.files = e.dataTransfer.files;
        const fn = e.dataTransfer.files[0].name;
        document.getElementById('file-name').textContent = fn;
        zone.style.borderColor = 'var(--gold)';
      }
    });
  }
});

/* stripe cripter for checkout page */
/*
|--------------------------------------------------------------------------
| STRIPE INIT
|--------------------------------------------------------------------------
*/
// Safely inject the key directly from Flask's render_template context
var publishableKeyStrp = "{{ stripe_publishable_key }}"; 
var stripe; 
var elements;
var card;

function initStripe(){
    if (stripe) return; // Prevent double initialization

    stripe = Stripe(publishableKeyStrp);
    elements = stripe.elements();

    card = elements.create("card", {
        style: {
            base: {
                fontSize: "16px",
                color: "#32325d",
                fontFamily: "Arial, sans-serif",
                "::placeholder": { color: "#a0aec0" }
            },
            invalid: { color: "#e53e3e" }
        }
    });
    card.mount("#card-element");
}

/* Binance integration for checkout page */
require('dotenv').config();
const express = require('express');
const axios = require('axios');
const crypto = require('crypto');

const app = express();
app.use(express.json());

const API_KEY = process.env.BINANCE_API_KEY;
const SECRET_KEY = process.env.BINANCE_SECRET_KEY;

// ─────────────────────────────────────────────
// BINANCE SIGNATURE
// ─────────────────────────────────────────────
function createSignature(timestamp, nonce, bodyString) {
  const payload = timestamp + "\n" + nonce + "\n" + bodyString + "\n";

  return crypto
    .createHmac("sha512", SECRET_KEY)
    .update(payload)
    .digest("hex")
    .toUpperCase();
}

// ─────────────────────────────────────────────
// CREATE BINANCE PAYMENT
// ─────────────────────────────────────────────
app.post("/create-payment", async (req, res) => {
  try {
    const { photoId, photoName, amount } = req.body;

    const order = {
      env: {
        terminalType: "WEB"
      },
      merchantTradeNo: `PHOTO_${Date.now()}`,
      orderAmount: amount,
      currency: "USDT",
      goods: {
        goodsType: "01",
        goodsCategory: "D000",
        referenceGoodsId: photoId,
        goodsName: photoName
      },
      returnUrl: "http://localhost:3000/payment-success",
      cancelUrl: "http://localhost:3000/payment-cancel"
    };

    const bodyString = JSON.stringify(order);
    const timestamp = Date.now().toString();
    const nonce = crypto.randomBytes(16).toString("hex");

    const signature = createSignature(timestamp, nonce, bodyString);

    const response = await axios.post(
      "https://bpay.binanceapi.com/binancepay/openapi/v2/order",
      order,
      {
        headers: {
          "Content-Type": "application/json",
          "BinancePay-Timestamp": timestamp,
          "BinancePay-Nonce": nonce,
          "BinancePay-Certificate-SN": API_KEY,
          "BinancePay-Signature": signature
        }
      }
    );

    const checkoutUrl = response.data?.data?.checkoutUrl;

    return res.json({
      success: true,
      checkoutUrl
    });

  } catch (error) {
    console.error("Binance error:", error.response?.data || error.message);

    return res.status(500).json({
      success: false,
      error: "Payment creation failed"
    });
  }
});

app.listen(process.env.PORT || 5000, () => {
  console.log("Server running...");
});

/*
|--------------------------------------------------------------------------
| TRIGGER MODAL
|--------------------------------------------------------------------------
*/
function purchaseThisProductNow(productId){
    initStripe();    
    document.getElementById("modalPayNowStripe").style.display = "flex";
         
    if(!productId){
        alert("Product Required!!!!");
        return;
    }  
    document.getElementById("productInQuestionId").value = productId;  
}

// Simulated click/trigger for testing
setTimeout(function(){
    purchaseThisProductNow(3);
}, 2000);

/*
|--------------------------------------------------------------------------
| FORM SUBMIT HANDLING
|--------------------------------------------------------------------------
*/
var form = document.getElementById("paymentForm");
var statusBox = document.getElementById("statusBox");

form.addEventListener("submit", function(e){
    e.preventDefault();
    statusBox.style.display = "none";

    var prodIdentity = document.getElementById("productInQuestionId").value;
    if(!prodIdentity){
        alert("There is a problem with the order you selected!!");
        return;
    }

    var subBtn = document.getElementById("payNowSubmitBtn");
    subBtn.textContent = "Processing....";
    subBtn.disabled = true; // Use boolean, not a string

    // Generate payment method token using Stripe Elements
    stripe.createPaymentMethod({
        type: "card",
        card: card,
        billing_details: {
            name: document.getElementById("cardName").value,
            address: {
                postal_code: document.getElementById("postalCode").value
            }
        }
    })
    .then(function(result){
        if(result.error){
            showError(result.error.message);
            subBtn.disabled = false;
            subBtn.textContent = "Pay Now";
            return;
        }

        // Prepare data for Python Flask backend
        var formData = new FormData();
        formData.append("payment_method", result.paymentMethod.id);
        formData.append("ProductId", prodIdentity);

        // Fetch sent directly to your Python server endpoint
        fetch("/charge", {
            method: "POST",
            body: formData
        })
        .then(function(response){
            return response.json();
        })
        .then(function(data){
            subBtn.disabled = false;
            subBtn.textContent = "Pay Now";

            if(data.success){
                showSuccess("Payment successful! Payment ID: " + data.payment_intent);
                
                // Optional: Redirect to your success template after 2 seconds
                setTimeout(function(){
                    window.location.href = "/payment_success.html"; 
                }, 2000);
            } else {
                if(data.response && data.response.error){
                    showError(data.response.error.message);
                } else {
                    showError("Payment failed");
                }
            }
        })
        .catch(function(error){
            subBtn.disabled = false;
            subBtn.textContent = "Pay Now";
            showError("Server Connection Error.");
        });
    });
});

function showSuccess(message){
    statusBox.className = "status success";
    statusBox.style.display = "block";
    statusBox.innerHTML = message;
}

function showError(message){
    statusBox.className = "status error";
    statusBox.style.display = "block";
    statusBox.innerHTML = message;
}

//Disable right click context menu on images
document.addEventListener('contextmenu', function(e){
   e.preventDefault();
});

//Disable drag and drop on images
document.addEventListener('dragstart', function(e){
    if(e.target.tagName === 'IMG'){
        e.preventDefault();
    }
});


// ── Fade-up on scroll ─────────────────────────────────────────────────────────
(function() {
  const observer = new IntersectionObserver(
    entries => entries.forEach(e => { if (e.isIntersecting) e.target.classList.add('visible'); }),
    { threshold: 0.1, rootMargin: '0px 0px -50px 0px' }
  );
  document.querySelectorAll('.fade-up').forEach(el => observer.observe(el));
})();

// ── Sticky nav shadow ─────────────────────────────────────────────────────────
window.addEventListener('scroll', function() {
  const nav = document.querySelector('.nav');
  if (nav) nav.classList.toggle('nav-scrolled', window.scrollY > 20);
}, { passive: true });

// ── Gallery search: live filter (client-side for instant UX) ──────────────────
const gallerySearchInput = document.querySelector('.gallery-search-wrap input');
if (gallerySearchInput) {
  const cards = document.querySelectorAll('#photo-grid .photo-card, #video-grid .photo-card');
  gallerySearchInput.addEventListener('input', function() {
    const q = this.value.toLowerCase().trim();
    cards.forEach(card => {
      const text = card.querySelector('h3')?.textContent.toLowerCase() || '';
      const cat  = card.querySelector('p')?.textContent.toLowerCase() || '';
      card.style.display = (!q || text.includes(q) || cat.includes(q)) ? '' : 'none';
    });
  });
}

// ── Lightbox for photos ───────────────────────────────────────────────────────
(function() {
  const lb = document.createElement('div');
  lb.id = 'lightbox';
  lb.style.cssText = 'display:none;position:fixed;inset:0;z-index:9999;background:rgba(0,0,0,0.95);cursor:zoom-out;align-items:center;justify-content:center;';
  lb.innerHTML = '<img id="lb-img" style="max-width:90vw;max-height:90vh;border-radius:8px;box-shadow:0 24px 80px rgba(0,0,0,0.8);">' +
                 '<button style="position:absolute;top:1.5rem;right:1.5rem;background:none;border:none;color:#fff;font-size:2rem;cursor:pointer;" onclick="closeLightbox()">✕</button>';
  document.body.appendChild(lb);

  window.openLightbox = function(src) {
    document.getElementById('lb-img').src = src;
    lb.style.display = 'flex';
  };
  window.closeLightbox = function() { lb.style.display = 'none'; };
  lb.addEventListener('click', function(e) { if (e.target === lb) closeLightbox(); });

  // ESC key
  document.addEventListener('keydown', function(e) { if (e.key === 'Escape') closeLightbox(); });
})();

// ── Video card: auto-play preview on hover ────────────────────────────────────
document.querySelectorAll('.video-thumb-wrap').forEach(function(wrap) {
  // Only auto-preview if there's a data-preview-src attribute set on the card
  const src = wrap.dataset.previewSrc;
  if (!src) return;
  let vid;
  wrap.addEventListener('mouseenter', function() {
    if (vid) return;
    const img = wrap.querySelector('img');
    vid = document.createElement('video');
    vid.src = src;
    vid.muted = true;
    vid.autoplay = true;
    vid.loop = true;
    vid.playsInline = true;
    vid.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;object-fit:cover;border-radius:inherit;';
    if (img) img.style.opacity = '0';
    wrap.style.position = 'relative';
    wrap.insertBefore(vid, wrap.firstChild);
  });
  wrap.addEventListener('mouseleave', function() {
    if (vid) { vid.remove(); vid = null; }
    const img = wrap.querySelector('img');
    if (img) img.style.opacity = '1';
  });
});

// ── Copy-to-clipboard helper (for share links) ────────────────────────────────
window.copyToClipboard = function(text, btn) {
  navigator.clipboard.writeText(text).then(function() {
    if (btn) { const orig = btn.textContent; btn.textContent = '✓ Copied!'; setTimeout(() => btn.textContent = orig, 2000); }
  });
};

// ── Flash message auto-dismiss ────────────────────────────────────────────────
document.querySelectorAll('.flash').forEach(function(el) {
  setTimeout(function() {
    el.style.transition = 'opacity .5s';
    el.style.opacity = '0';
    setTimeout(() => el.remove(), 500);
  }, 4000);
});