from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak,
    Table, TableStyle, HRFlowable, KeepTogether
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate
from reportlab.lib.units import inch
import datetime

# ── Colour palette ──────────────────────────────────────────────────────────
DARK_BLUE   = colors.HexColor("#0D1B2A")
MID_BLUE    = colors.HexColor("#1B4F72")
ACCENT      = colors.HexColor("#2E86AB")
LIGHT_BLUE  = colors.HexColor("#D6EAF8")
GREEN       = colors.HexColor("#1E8449")
LIGHT_GREEN = colors.HexColor("#D5F5E3")
ORANGE      = colors.HexColor("#D35400")
LIGHT_ORANGE= colors.HexColor("#FDEBD0")
RED         = colors.HexColor("#C0392B")
LIGHT_RED   = colors.HexColor("#FADBD8")
GREY_LIGHT  = colors.HexColor("#F2F3F4")
GREY_MID    = colors.HexColor("#BDC3C7")
WHITE       = colors.white
BLACK       = colors.black

PAGE_W, PAGE_H = A4

# ── Style definitions ────────────────────────────────────────────────────────
base = getSampleStyleSheet()

def make_styles():
    s = {}
    s["cover_title"] = ParagraphStyle("cover_title", fontSize=32, textColor=WHITE,
        alignment=TA_CENTER, fontName="Helvetica-Bold", spaceAfter=10, leading=38)
    s["cover_sub"] = ParagraphStyle("cover_sub", fontSize=16, textColor=LIGHT_BLUE,
        alignment=TA_CENTER, fontName="Helvetica", spaceAfter=6, leading=20)
    s["cover_info"] = ParagraphStyle("cover_info", fontSize=12, textColor=GREY_MID,
        alignment=TA_CENTER, fontName="Helvetica", spaceAfter=4)

    s["h1"] = ParagraphStyle("h1", fontSize=22, textColor=DARK_BLUE,
        fontName="Helvetica-Bold", spaceBefore=18, spaceAfter=8, leading=28)
    s["h2"] = ParagraphStyle("h2", fontSize=16, textColor=MID_BLUE,
        fontName="Helvetica-Bold", spaceBefore=14, spaceAfter=6, leading=20)
    s["h3"] = ParagraphStyle("h3", fontSize=13, textColor=ACCENT,
        fontName="Helvetica-Bold", spaceBefore=10, spaceAfter=4, leading=16)
    s["h4"] = ParagraphStyle("h4", fontSize=11, textColor=DARK_BLUE,
        fontName="Helvetica-BoldOblique", spaceBefore=8, spaceAfter=3)

    s["body"] = ParagraphStyle("body", fontSize=10, textColor=BLACK,
        fontName="Helvetica", spaceAfter=6, leading=15, alignment=TA_JUSTIFY)
    s["body_bold"] = ParagraphStyle("body_bold", fontSize=10, textColor=BLACK,
        fontName="Helvetica-Bold", spaceAfter=6, leading=15)
    s["bullet"] = ParagraphStyle("bullet", fontSize=10, textColor=BLACK,
        fontName="Helvetica", spaceAfter=4, leading=14, leftIndent=18,
        bulletIndent=6)
    s["bullet2"] = ParagraphStyle("bullet2", fontSize=10, textColor=BLACK,
        fontName="Helvetica", spaceAfter=3, leading=13, leftIndent=36,
        bulletIndent=24)

    s["code"] = ParagraphStyle("code", fontSize=8.5, textColor=DARK_BLUE,
        fontName="Courier", spaceAfter=3, leading=12, leftIndent=10,
        backColor=GREY_LIGHT)
    s["code_comment"] = ParagraphStyle("code_comment", fontSize=8.5, textColor=GREEN,
        fontName="Courier", spaceAfter=3, leading=12, leftIndent=10,
        backColor=GREY_LIGHT)

    s["note_box"] = ParagraphStyle("note_box", fontSize=10, textColor=DARK_BLUE,
        fontName="Helvetica", spaceAfter=4, leading=14, leftIndent=8)
    s["tip_box"] = ParagraphStyle("tip_box", fontSize=10, textColor=GREEN,
        fontName="Helvetica", spaceAfter=4, leading=14, leftIndent=8)
    s["warn_box"] = ParagraphStyle("warn_box", fontSize=10, textColor=RED,
        fontName="Helvetica", spaceAfter=4, leading=14, leftIndent=8)

    s["chapter_num"] = ParagraphStyle("chapter_num", fontSize=13, textColor=ACCENT,
        fontName="Helvetica-Bold", spaceAfter=2, alignment=TA_CENTER)
    s["chapter_title"] = ParagraphStyle("chapter_title", fontSize=26, textColor=DARK_BLUE,
        fontName="Helvetica-Bold", spaceAfter=8, alignment=TA_CENTER, leading=30)

    s["toc_chapter"] = ParagraphStyle("toc_chapter", fontSize=11, textColor=DARK_BLUE,
        fontName="Helvetica-Bold", spaceAfter=3, leading=14)
    s["toc_section"] = ParagraphStyle("toc_section", fontSize=10, textColor=MID_BLUE,
        fontName="Helvetica", spaceAfter=2, leading=13, leftIndent=16)

    s["qa"] = ParagraphStyle("qa", fontSize=10, textColor=BLACK,
        fontName="Helvetica", spaceAfter=5, leading=14, leftIndent=12)
    s["q_label"] = ParagraphStyle("q_label", fontSize=10, textColor=MID_BLUE,
        fontName="Helvetica-Bold", spaceAfter=2, leading=14)
    s["a_label"] = ParagraphStyle("a_label", fontSize=10, textColor=GREEN,
        fontName="Helvetica-Bold", spaceAfter=2, leading=14)

    s["summary"] = ParagraphStyle("summary", fontSize=10, textColor=DARK_BLUE,
        fontName="Helvetica", spaceAfter=5, leading=14, leftIndent=10,
        backColor=LIGHT_BLUE)
    s["exercise"] = ParagraphStyle("exercise", fontSize=10, textColor=DARK_BLUE,
        fontName="Helvetica", spaceAfter=5, leading=14, leftIndent=10)

    s["footer"] = ParagraphStyle("footer", fontSize=8, textColor=GREY_MID,
        fontName="Helvetica", alignment=TA_CENTER)
    return s

ST = make_styles()

# ── Helper builders ──────────────────────────────────────────────────────────

def H1(text):
    return [HRFlowable(width="100%", thickness=2, color=ACCENT, spaceAfter=4),
            Paragraph(text, ST["h1"])]

def H2(text): return [Paragraph(text, ST["h2"])]
def H3(text): return [Paragraph(text, ST["h3"])]
def H4(text): return [Paragraph(text, ST["h4"])]
def P(text):  return [Paragraph(text, ST["body"])]
def PB(text): return [Paragraph(text, ST["body_bold"])]
def SP(n=8):  return [Spacer(1, n)]
def PBR():    return [PageBreak()]

def B(text): return [Paragraph(f"&#8226;  {text}", ST["bullet"])]
def B2(text): return [Paragraph(f"&#8211;  {text}", ST["bullet2"])]

def code_block(lines):
    result = []
    for line in lines:
        style = ST["code_comment"] if line.strip().startswith("#") else ST["code"]
        safe = line.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
        result.append(Paragraph(safe if safe else "&nbsp;", style))
    return result

def note(text):
    return [Table([[Paragraph(f"&#128161; <b>NOTE:</b> {text}", ST["note_box"])]],
        colWidths=["100%"],
        style=TableStyle([("BACKGROUND",(0,0),(-1,-1),LIGHT_BLUE),
                          ("BOX",(0,0),(-1,-1),1,ACCENT),
                          ("LEFTPADDING",(0,0),(-1,-1),8),
                          ("RIGHTPADDING",(0,0),(-1,-1),8),
                          ("TOPPADDING",(0,0),(-1,-1),6),
                          ("BOTTOMPADDING",(0,0),(-1,-1),6)]))]

def tip(text):
    return [Table([[Paragraph(f"&#9989; <b>TIP:</b> {text}", ST["tip_box"])]],
        colWidths=["100%"],
        style=TableStyle([("BACKGROUND",(0,0),(-1,-1),LIGHT_GREEN),
                          ("BOX",(0,0),(-1,-1),1,GREEN),
                          ("LEFTPADDING",(0,0),(-1,-1),8),
                          ("RIGHTPADDING",(0,0),(-1,-1),8),
                          ("TOPPADDING",(0,0),(-1,-1),6),
                          ("BOTTOMPADDING",(0,0),(-1,-1),6)]))]

def warn(text):
    return [Table([[Paragraph(f"&#9888; <b>WARNING:</b> {text}", ST["warn_box"])]],
        colWidths=["100%"],
        style=TableStyle([("BACKGROUND",(0,0),(-1,-1),LIGHT_RED),
                          ("BOX",(0,0),(-1,-1),1,RED),
                          ("LEFTPADDING",(0,0),(-1,-1),8),
                          ("RIGHTPADDING",(0,0),(-1,-1),8),
                          ("TOPPADDING",(0,0),(-1,-1),6),
                          ("BOTTOMPADDING",(0,0),(-1,-1),6)]))]

def chapter_header(num, title, subtitle=""):
    items = []
    items += PBR()
    items.append(Table([[""]], colWidths=["100%"], rowHeights=[6],
        style=TableStyle([("BACKGROUND",(0,0),(-1,-1),ACCENT)])))
    items += SP(20)
    items.append(Paragraph(f"CHAPTER {num}", ST["chapter_num"]))
    items.append(Paragraph(title, ST["chapter_title"]))
    if subtitle:
        items.append(Paragraph(subtitle, ParagraphStyle("cs", fontSize=12,
            textColor=GREY_MID, fontName="Helvetica-Oblique",
            alignment=TA_CENTER, spaceAfter=6)))
    items += SP(6)
    items.append(Table([[""]], colWidths=["100%"], rowHeights=[3],
        style=TableStyle([("BACKGROUND",(0,0),(-1,-1),LIGHT_BLUE)])))
    items += SP(14)
    return items

def definition_box(term, definition):
    rows = [[Paragraph(f"<b>{term}</b>", ST["body_bold"]),
             Paragraph(definition, ST["body"])]]
    return [Table(rows, colWidths=[3.5*cm, 12*cm],
        style=TableStyle([("BACKGROUND",(0,0),(0,0),LIGHT_BLUE),
                          ("GRID",(0,0),(-1,-1),0.5,GREY_MID),
                          ("VALIGN",(0,0),(-1,-1),"TOP"),
                          ("LEFTPADDING",(0,0),(-1,-1),6),
                          ("RIGHTPADDING",(0,0),(-1,-1),6),
                          ("TOPPADDING",(0,0),(-1,-1),5),
                          ("BOTTOMPADDING",(0,0),(-1,-1),5)]))]

def summary_box(points):
    items = [Paragraph("<b>Chapter Summary</b>", ST["h3"])]
    for p in points:
        items.append(Paragraph(f"&#10003;  {p}", ST["summary"]))
    return items

def exercise_box(title, items_list):
    result = []
    result.append(Table([[Paragraph(f"&#128203; <b>{title}</b>", ST["h3"])]],
        colWidths=["100%"],
        style=TableStyle([("BACKGROUND",(0,0),(-1,-1),LIGHT_ORANGE),
                          ("BOX",(0,0),(-1,-1),1,ORANGE),
                          ("LEFTPADDING",(0,0),(-1,-1),8),
                          ("TOPPADDING",(0,0),(-1,-1),6),
                          ("BOTTOMPADDING",(0,0),(-1,-1),6)])))
    for i, item in enumerate(items_list, 1):
        result.append(Paragraph(f"{i}. {item}", ST["exercise"]))
    return result

def two_col_table(headers, rows, col_widths=None):
    if col_widths is None:
        col_widths = [5*cm, 10.5*cm]
    data = [[Paragraph(f"<b>{h}</b>", ST["body_bold"]) for h in headers]]
    for row in rows:
        data.append([Paragraph(str(c), ST["body"]) for c in row])
    ts = TableStyle([
        ("BACKGROUND",(0,0),(-1,0),MID_BLUE),
        ("TEXTCOLOR",(0,0),(-1,0),WHITE),
        ("GRID",(0,0),(-1,-1),0.5,GREY_MID),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[WHITE, GREY_LIGHT]),
        ("LEFTPADDING",(0,0),(-1,-1),6),
        ("RIGHTPADDING",(0,0),(-1,-1),6),
        ("TOPPADDING",(0,0),(-1,-1),4),
        ("BOTTOMPADDING",(0,0),(-1,-1),4),
        ("VALIGN",(0,0),(-1,-1),"TOP"),
    ])
    return [Table(data, colWidths=col_widths, style=ts)]

def ascii_diagram(lines):
    result = []
    for line in lines:
        safe = line.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
        result.append(Paragraph(safe if safe else "&nbsp;", ST["code"]))
    return result

def interview_q(n, q, a):
    return [
        Paragraph(f"<b>Q{n}.</b> {q}", ST["q_label"]),
        Paragraph(f"<b>Answer:</b> {a}", ST["qa"]),
        SP(4),
    ]

# ═══════════════════════════════════════════════════════════════════════════════
# DOCUMENT CONTENT
# ═══════════════════════════════════════════════════════════════════════════════

def build_content():
    story = []

    # ── COVER PAGE ────────────────────────────────────────────────────────────
    story.append(Spacer(1, 1.5*cm))
    cover_header = Table([[""]], colWidths=["100%"], rowHeights=[8],
        style=TableStyle([("BACKGROUND",(0,0),(-1,-1),ACCENT)]))
    story.append(cover_header)
    story.append(Spacer(1, 0.5*cm))

    cover_bg = Table([[
        Paragraph("REST APIs &amp; FastAPI", ST["cover_title"]),
    ]], colWidths=["100%"],
    style=TableStyle([("BACKGROUND",(0,0),(-1,-1),DARK_BLUE),
                      ("TOPPADDING",(0,0),(-1,-1),40),
                      ("BOTTOMPADDING",(0,0),(-1,-1),10),]))
    story.append(cover_bg)

    cover_sub_table = Table([[
        Paragraph("Using Python — Complete Professional Study Guide", ST["cover_sub"]),
    ]], colWidths=["100%"],
    style=TableStyle([("BACKGROUND",(0,0),(-1,-1),DARK_BLUE),
                      ("TOPPADDING",(0,0),(-1,-1),2),
                      ("BOTTOMPADDING",(0,0),(-1,-1),30)]))
    story.append(cover_sub_table)

    story.append(Table([[""]], colWidths=["100%"], rowHeights=[4],
        style=TableStyle([("BACKGROUND",(0,0),(-1,-1),ACCENT)])))
    story.append(Spacer(1, 1*cm))

    badges = [
        ["Beginner to Advanced", "20 Chapters", "Fraud Detection Focus"],
        ["100 Interview Qs", "50 Coding Exercises", "Real-World Projects"],
    ]
    for row in badges:
        badge_cells = [[Paragraph(f"<b>{b}</b>",
            ParagraphStyle("badge", fontSize=9, textColor=WHITE,
            fontName="Helvetica-Bold", alignment=TA_CENTER))] for b in row]
        story.append(Table([badge_cells], colWidths=[5.2*cm, 5.2*cm, 5.2*cm],
            style=TableStyle([("BACKGROUND",(0,0),(-1,-1),MID_BLUE),
                              ("GRID",(0,0),(-1,-1),1,WHITE),
                              ("TOPPADDING",(0,0),(-1,-1),6),
                              ("BOTTOMPADDING",(0,0),(-1,-1),6)])))
        story.append(Spacer(1, 0.3*cm))

    story.append(Spacer(1, 1*cm))
    story.append(Paragraph("Designed for Software Engineering Students &amp; Aspiring ML Engineers",
        ST["cover_info"]))
    story.append(Paragraph("Specialising in Fraud Detection Systems", ST["cover_info"]))
    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph(f"Edition 1.0 — {datetime.date.today().year}", ST["cover_info"]))
    story.append(PageBreak())

    # ── TABLE OF CONTENTS ─────────────────────────────────────────────────────
    story += H1("Table of Contents")
    toc_data = [
        ("Chapter 1",  "Introduction to APIs"),
        ("Chapter 2",  "HTTP Fundamentals"),
        ("Chapter 3",  "REST Architecture"),
        ("Chapter 4",  "Python Review for API Development"),
        ("Chapter 5",  "Introduction to FastAPI"),
        ("Chapter 6",  "Building CRUD Endpoints"),
        ("Chapter 7",  "Pydantic Models and Data Validation"),
        ("Chapter 8",  "Path Parameters"),
        ("Chapter 9",  "Query Parameters"),
        ("Chapter 10", "Dependency Injection"),
        ("Chapter 11", "Authentication — JWT, OAuth2 &amp; Password Hashing"),
        ("Chapter 12", "Databases with SQLAlchemy and Alembic"),
        ("Chapter 13", "Error Handling"),
        ("Chapter 14", "Middleware"),
        ("Chapter 15", "Background Tasks"),
        ("Chapter 16", "File Uploads"),
        ("Chapter 17", "Testing APIs with pytest"),
        ("Chapter 18", "Dockerising FastAPI"),
        ("Chapter 19", "Deploying FastAPI"),
        ("Chapter 20", "Capstone — Building a Fraud Detection API"),
        ("Appendix A", "100 Interview Questions with Answers"),
        ("Appendix B", "100 Quiz Questions"),
        ("Appendix C", "50 Practical Coding Exercises"),
        ("Appendix D", "20 Project Ideas"),
        ("Appendix E", "Career Roadmap, Glossary &amp; Cheat Sheets"),
    ]
    for ch, title in toc_data:
        story.append(Paragraph(f"<b>{ch}</b> — {title}", ST["toc_chapter"]))
    story += PBR()

    # ═══════════════════════════════════════════════
    # CHAPTER 1 — Introduction to APIs
    # ═══════════════════════════════════════════════
    story += chapter_header("1", "Introduction to APIs",
        "Understanding what APIs are, why they exist, and how they shape the modern world")

    story += H2("1.1 What Is an API?")
    story += P("API stands for <b>Application Programming Interface</b>. Before we dive into the technical definition, let's use a real-world analogy that will make this concept instantly clear.")
    story += P("Imagine you walk into a restaurant. You (the customer) don't walk into the kitchen and cook your own food. Instead, you look at a <b>menu</b>, choose what you want, and a <b>waiter</b> takes your order to the kitchen. The kitchen prepares your food and the waiter brings it back to you.")
    story += P("In this analogy:")
    story += B("You are the <b>client</b> (or the application requesting data)")
    story += B("The waiter is the <b>API</b>")
    story += B("The kitchen is the <b>server</b> (where data and logic live)")
    story += B("The menu is the <b>API documentation</b>")
    story += SP()
    story += definition_box("API", "A set of rules, protocols, and tools that allows one software application to communicate with another. It defines the methods and data formats that applications use to request and exchange information.")
    story += SP()
    story += P("APIs are everywhere in modern software. Every time you log in with Google, check the weather on your phone, or receive a fraud alert from your bank — an API is working behind the scenes.")

    story += H2("1.2 Why APIs Exist")
    story += P("APIs exist to solve a fundamental problem in software engineering: <b>how do different systems talk to each other without sharing their internal code?</b>")
    story += P("Consider a bank's core system. It stores millions of sensitive transactions, customer accounts, and financial records. The bank wants to:")
    story += B("Let mobile apps display account balances")
    story += B("Allow merchants to process payments")
    story += B("Share transaction data with fraud detection systems")
    story += B("Connect to government reporting systems")
    story += SP()
    story += P("Without APIs, every single one of these integrations would require direct access to the bank's internal database — a massive security risk. APIs create a <b>controlled, secure interface</b> that exposes only the data and functionality that should be shared.")
    story += SP()
    story += note("APIs enforce the software engineering principle of <b>Separation of Concerns</b>. The frontend doesn't need to know HOW the backend stores data — it just needs to know WHAT to ask for and WHAT it will receive.")

    story += H2("1.3 Real-World API Examples")
    story += two_col_table(
        ["Company / Service", "How They Use APIs"],
        [
            ["Google Maps", "Provides a Maps API so apps like Uber and Bolt can embed maps and get directions"],
            ["Mpesa (Safaricom)", "Daraja API allows developers to send/receive money, check balances, and query transactions"],
            ["Stripe", "Payment API that lets any website accept credit card payments without handling card data directly"],
            ["Twitter / X", "REST API lets apps post tweets, fetch timelines, and analyse trends"],
            ["Fraud Detection (Banks)", "Internal APIs connect transaction processors to ML fraud-scoring models in real time"],
            ["OpenAI", "Provides an API to use GPT models — the same API that powers ChatGPT integrations"],
        ],
        [5*cm, 10.5*cm]
    )

    story += H2("1.4 API vs Website")
    story += P("Many beginners confuse APIs with websites. Here is a clear distinction:")
    story += two_col_table(
        ["Feature", "Website", "API"],
        [
            ["Designed for", "Human users (via browser)", "Software applications (via code)"],
            ["Returns", "HTML pages (visual)", "Structured data (JSON/XML)"],
            ["Interaction", "Clicking buttons, forms", "HTTP requests from code"],
            ["Authentication", "Username/password (session)", "API keys, tokens (JWT)"],
            ["Example", "www.mybank.com", "api.mybank.com/transactions"],
        ],
        [4*cm, 6*cm, 5.5*cm]
    )

    story += H2("1.5 API vs Library")
    story += P("Another common confusion is between an API and a library.")
    story += P("A <b>library</b> (like NumPy or Pandas) is code you download and run <i>inside your own application</i>. An <b>API</b> is a service running on a <i>remote server</i> that you communicate with over the network.")
    story += two_col_table(
        ["Feature", "Library", "API"],
        [
            ["Where it runs", "Inside your application", "On a remote server"],
            ["Communication", "Direct function calls", "HTTP requests"],
            ["Requires internet?", "No (after install)", "Usually yes"],
            ["Example", "import pandas as pd", "requests.get('https://api.example.com')"],
        ],
        [4*cm, 5.5*cm, 6*cm]
    )

    story += H2("1.6 Client and Server Architecture")
    story += P("Understanding the Client-Server model is fundamental to understanding APIs. Let's look at the architecture:")
    story += SP()
    story += ascii_diagram([
        "  +------------------+        HTTP Request          +------------------+",
        "  |                  |  --------------------------> |                  |",
        "  |    CLIENT        |                              |     SERVER       |",
        "  |  (Browser/App/   |  <--------------------------  | (FastAPI App /   |",
        "  |   Mobile/Script) |        HTTP Response         |  Database)       |",
        "  +------------------+                              +------------------+",
        "         |                                                   |",
        "  Makes requests                                    Processes requests",
        "  Receives data                                     Returns responses",
        "  Displays to user                                  Stores/retrieves data",
    ])
    story += SP()
    story += P("The <b>Client</b> is any application that sends a request. This could be a mobile banking app, a fraud monitoring dashboard, a Python script, or even another API.")
    story += P("The <b>Server</b> is where the API lives. It processes incoming requests, runs business logic (such as fraud scoring), queries databases, and returns responses.")

    story += H2("1.7 HTTP Overview")
    story += P("<b>HTTP</b> (HyperText Transfer Protocol) is the foundation of all data communication on the web. Every API call you make uses HTTP. It is a <b>request-response protocol</b> — a client sends a request, the server sends a response.")
    story += P("HTTP is <b>stateless</b> — each request is independent. The server does not remember previous requests. This is why we need mechanisms like tokens and sessions to maintain identity across multiple requests.")
    story += SP()
    story += note("HTTPS is the secure, encrypted version of HTTP. All production APIs must use HTTPS to protect data in transit. FastAPI works with both, but always deploy with HTTPS.")
    story += SP()
    story += P("An HTTP request consists of:")
    story += B("<b>Method</b> — What action to perform (GET, POST, PUT, DELETE, etc.)")
    story += B("<b>URL</b> — Where to send the request (e.g., https://api.fraud-detector.com/transactions)")
    story += B("<b>Headers</b> — Metadata about the request (Content-Type, Authorization, etc.)")
    story += B("<b>Body</b> — Data sent with the request (for POST/PUT only)")
    story += SP()

    story += summary_box([
        "An API (Application Programming Interface) allows software systems to communicate in a controlled, secure way.",
        "APIs separate the frontend (what the user sees) from the backend (where data lives and logic runs).",
        "Real-world examples include payment APIs (Mpesa, Stripe), mapping APIs (Google Maps), and fraud detection APIs used by banks.",
        "HTTP is the protocol that powers all web API communication.",
        "The Client-Server architecture defines who makes requests (client) and who responds (server).",
        "A library runs inside your app; an API runs on a remote server — this is a key distinction.",
    ])
    story += SP()
    story += exercise_box("Chapter 1 Exercises", [
        "In your own words, explain what an API is to a non-technical friend using a real-life analogy from Kenya (e.g., Mpesa, matatu SACCO).",
        "List five mobile apps you use daily and identify which external APIs they likely use.",
        "Research the Safaricom Daraja API. What endpoints does it expose? What authentication does it use?",
        "Explain the difference between a REST API and a library with a concrete Python example.",
        "Draw a client-server diagram for a fraud detection system where a bank app sends transaction data to a fraud scoring service.",
    ])
    story += PBR()

    # ═══════════════════════════════════════════════
    # CHAPTER 2 — HTTP Fundamentals
    # ═══════════════════════════════════════════════
    story += chapter_header("2", "HTTP Fundamentals",
        "Master the building blocks every API developer must know")

    story += H2("2.1 HTTP Methods")
    story += P("HTTP defines a set of <b>request methods</b> (also called <b>verbs</b>) that indicate what action the client wants to perform on a resource. Think of them as commands.")

    story += H3("GET — Retrieve Data")
    story += P("GET requests are used to <b>read or retrieve</b> data from the server. They should <b>never modify</b> any data. GET requests are safe and idempotent (calling them multiple times gives the same result).")
    story += P("<b>Real-world example:</b> A fraud analyst's dashboard requests the last 100 transactions for a customer.")
    story += code_block([
        "# GET request using Python requests library",
        "import requests",
        "",
        "# Retrieve all transactions for a customer",
        "response = requests.get(",
        "    'https://api.fraudsystem.com/transactions',",
        "    headers={'Authorization': 'Bearer eyJhbGciOiJIUzI1NiJ9...'},",
        "    params={'customer_id': 'KE-002341', 'limit': 100}",
        ")",
        "",
        "# Print the status code",
        "print(response.status_code)   # 200 means success",
        "print(response.json())        # The actual transaction data",
    ])

    story += H3("POST — Create New Data")
    story += P("POST requests are used to <b>create new resources</b> on the server. Unlike GET, POST sends data in the <b>request body</b>. POST is <b>not idempotent</b> — submitting the same POST twice creates two resources.")
    story += P("<b>Real-world example:</b> A merchant's point-of-sale system submits a new transaction for fraud analysis.")
    story += code_block([
        "# POST request — submit a new transaction for fraud scoring",
        "import requests",
        "import json",
        "",
        "transaction_data = {",
        "    'amount': 75000.00,          # Amount in Kenyan Shillings",
        "    'currency': 'KES',",
        "    'merchant': 'Electronics Hub Nairobi',",
        "    'customer_id': 'KE-002341',",
        "    'location': 'Westlands, Nairobi',",
        "    'timestamp': '2024-06-15T14:30:00Z'",
        "}",
        "",
        "response = requests.post(",
        "    'https://api.fraudsystem.com/transactions',",
        "    json=transaction_data,   # Automatically sets Content-Type: application/json",
        "    headers={'Authorization': 'Bearer eyJhbGciOiJIUzI1NiJ9...'}",
        ")",
        "",
        "result = response.json()",
        "print(result['fraud_score'])   # e.g., 0.89 — high risk!",
        "print(result['risk_level'])    # e.g., 'HIGH'",
    ])

    story += H3("PUT — Replace a Resource")
    story += P("PUT requests <b>completely replace</b> an existing resource. If you send a PUT request, you must include ALL fields of the resource — any fields you omit will be removed or set to null.")
    story += P("<b>Real-world example:</b> Update all the details of a customer's risk profile.")
    story += code_block([
        "# PUT — replace the full customer risk profile",
        "updated_profile = {",
        "    'customer_id': 'KE-002341',",
        "    'risk_score': 7.8,",
        "    'risk_category': 'HIGH',",
        "    'flagged': True,",
        "    'notes': 'Multiple high-value transactions in 24 hours',",
        "    'reviewed_by': 'analyst_jane'",
        "}",
        "",
        "response = requests.put(",
        "    'https://api.fraudsystem.com/customers/KE-002341/profile',",
        "    json=updated_profile,",
        "    headers={'Authorization': 'Bearer ...'}",
        ")",
    ])

    story += H3("PATCH — Partially Update a Resource")
    story += P("PATCH requests are used to <b>partially update</b> a resource. Unlike PUT, you only send the fields you want to change. This is more efficient for small updates.")
    story += P("<b>Real-world example:</b> Update only the fraud flag status of a transaction.")
    story += code_block([
        "# PATCH — update only the fraud flag",
        "patch_data = {",
        "    'flagged': True,",
        "    'reviewed': True",
        "}",
        "",
        "response = requests.patch(",
        "    'https://api.fraudsystem.com/transactions/TXN-9982',",
        "    json=patch_data,",
        "    headers={'Authorization': 'Bearer ...'}",
        ")",
    ])

    story += H3("DELETE — Remove a Resource")
    story += P("DELETE requests <b>remove a resource</b> from the server. A successful DELETE typically returns 204 (No Content) or 200 (OK) with a confirmation message.")
    story += code_block([
        "# DELETE — remove a test transaction from the system",
        "response = requests.delete(",
        "    'https://api.fraudsystem.com/transactions/TEST-001',",
        "    headers={'Authorization': 'Bearer ...'}",
        ")",
        "print(response.status_code)   # 204 No Content — deleted successfully",
    ])

    story += H3("Other Methods: OPTIONS and HEAD")
    story += P("<b>OPTIONS</b> is used by browsers to check what HTTP methods a server supports before making a cross-origin request (CORS preflight). <b>HEAD</b> is identical to GET but returns only the headers, not the body — useful for checking if a resource exists without downloading it.")

    story += H2("2.2 HTTP Status Codes")
    story += P("HTTP status codes are 3-digit numbers that tell the client what happened with their request. They are grouped into five categories:")
    story += two_col_table(
        ["Range", "Category", "Meaning"],
        [
            ["1xx", "Informational", "Request received, processing continues"],
            ["2xx", "Success", "Request was successfully received and processed"],
            ["3xx", "Redirection", "Further action needed (redirect to another URL)"],
            ["4xx", "Client Error", "The client made a mistake in the request"],
            ["5xx", "Server Error", "The server failed to process a valid request"],
        ],
        [2*cm, 4*cm, 9.5*cm]
    )
    story += SP()
    story += two_col_table(
        ["Code", "Name", "When It Occurs in a Fraud API"],
        [
            ["200", "OK", "Transaction retrieved or fraud score returned successfully"],
            ["201", "Created", "New transaction submitted and fraud analysis started"],
            ["204", "No Content", "Transaction deleted, no body returned"],
            ["400", "Bad Request", "Transaction data is missing required fields"],
            ["401", "Unauthorised", "Missing or invalid JWT token in Authorization header"],
            ["403", "Forbidden", "Token is valid but user lacks permission for this action"],
            ["404", "Not Found", "Transaction ID does not exist in the database"],
            ["409", "Conflict", "Duplicate transaction ID submitted"],
            ["422", "Unprocessable Entity", "JSON is valid but field values fail validation (e.g. negative amount)"],
            ["429", "Too Many Requests", "Rate limit exceeded — API abuse or DDoS attempt"],
            ["500", "Internal Server Error", "Unexpected crash in the fraud detection model"],
            ["503", "Service Unavailable", "ML model server is down for maintenance"],
        ],
        [1.5*cm, 4*cm, 10*cm]
    )

    story += H2("2.3 HTTP Request and Response Structure")
    story += H3("Anatomy of an HTTP Request")
    story += ascii_diagram([
        "  POST /transactions HTTP/1.1",
        "  Host: api.fraudsystem.com",
        "  Content-Type: application/json",
        "  Authorization: Bearer eyJhbGciOiJIUzI1NiJ9...",
        "  Accept: application/json",
        "  ",
        "  {",
        '    "amount": 75000.00,',
        '    "currency": "KES",',
        '    "customer_id": "KE-002341"',
        "  }",
        "  ",
        "  |______|  |_____________|  |________|",
        "   Method     Path/Endpoint   Protocol",
    ])

    story += H3("Anatomy of an HTTP Response")
    story += ascii_diagram([
        "  HTTP/1.1 201 Created",
        "  Content-Type: application/json",
        "  X-Request-ID: abc-123-def-456",
        "  ",
        "  {",
        '    "transaction_id": "TXN-9983",',
        '    "fraud_score": 0.89,',
        '    "risk_level": "HIGH",',
        '    "action": "BLOCK",',
        '    "message": "Transaction blocked due to high fraud risk"',
        "  }",
    ])

    story += H2("2.4 HTTP Headers")
    story += P("Headers are <b>key-value pairs</b> sent with every HTTP request and response. They carry metadata — information about the request or response itself, not the data being transferred.")
    story += two_col_table(
        ["Header", "Type", "Purpose in Fraud Detection API"],
        [
            ["Content-Type", "Request/Response", "Tells the receiver what format the body is in (application/json)"],
            ["Authorization", "Request", "Carries the JWT token: 'Bearer eyJ...'"],
            ["Accept", "Request", "What format the client can accept back (application/json)"],
            ["X-API-Key", "Request", "Alternative to JWT for machine-to-machine authentication"],
            ["X-Request-ID", "Request/Response", "Unique ID for tracing a request through distributed systems"],
            ["X-RateLimit-Remaining", "Response", "How many API calls the client has left this minute"],
            ["Cache-Control", "Response", "Tells clients not to cache sensitive fraud data"],
        ],
        [3.5*cm, 3*cm, 9*cm]
    )

    story += H2("2.5 Query Parameters")
    story += P("Query parameters are <b>key-value pairs appended to a URL</b> after a question mark (?). They are used to filter, sort, or paginate results in GET requests.")
    story += code_block([
        "# URL with query parameters",
        "# https://api.fraudsystem.com/transactions?customer_id=KE-002341&limit=10&page=2&status=flagged",
        "#                                          |___________________|  |_______| |______| |____________|",
        "#                                           Filter by customer   Page size  Page no.  Filter by status",
        "",
        "# In Python",
        "params = {",
        "    'customer_id': 'KE-002341',",
        "    'limit': 10,",
        "    'page': 2,",
        "    'status': 'flagged'",
        "}",
        "response = requests.get('https://api.fraudsystem.com/transactions', params=params)",
    ])

    story += H2("2.6 Path Parameters")
    story += P("Path parameters are <b>variable parts of the URL path</b> used to identify a specific resource. Unlike query parameters, they are part of the URL itself.")
    story += code_block([
        "# Path parameter examples",
        "# /transactions/{transaction_id}",
        "# /customers/{customer_id}/profile",
        "# /transactions/{transaction_id}/fraud-report",
        "",
        "# Accessing transaction TXN-9983",
        "response = requests.get(",
        "    'https://api.fraudsystem.com/transactions/TXN-9983',",
        "    headers={'Authorization': 'Bearer ...'}",
        ")",
    ])
    story += tip("Use path parameters to identify a specific resource (e.g., /transactions/TXN-9983). Use query parameters to filter or modify a collection (e.g., /transactions?status=flagged).")

    story += H2("2.7 JSON — The Universal Language of APIs")
    story += P("<b>JSON</b> (JavaScript Object Notation) is the most common data format used in modern APIs. Despite its name, it works with every programming language including Python.")
    story += P("JSON supports these data types:")
    story += B("String: <b>\"KE-002341\"</b>")
    story += B("Number: <b>75000.00</b> or <b>89</b>")
    story += B("Boolean: <b>true</b> or <b>false</b>")
    story += B("Null: <b>null</b>")
    story += B("Array: <b>[\"CARD\", \"MOBILE\", \"CASH\"]</b>")
    story += B("Object: <b>{\"key\": \"value\"}</b>")
    story += code_block([
        "# A typical fraud detection API response in JSON",
        "{",
        '  "transaction_id": "TXN-9983",',
        '  "customer_id": "KE-002341",',
        '  "amount": 75000.00,',
        '  "currency": "KES",',
        '  "fraud_score": 0.89,',
        '  "risk_level": "HIGH",',
        '  "flagged": true,',
        '  "flags": ["unusual_amount", "new_merchant", "rapid_succession"],',
        '  "timestamp": "2024-06-15T14:30:00Z",',
        '  "ml_model_version": "fraud-detector-v2.3",',
        '  "action": "BLOCK"',
        "}",
    ])
    story += code_block([
        "# Working with JSON in Python",
        "import json",
        "",
        "# Convert Python dict to JSON string",
        "data = {'amount': 75000.00, 'flagged': True}",
        "json_str = json.dumps(data)   # '{\"amount\": 75000.0, \"flagged\": true}'",
        "",
        "# Convert JSON string to Python dict",
        "parsed = json.loads(json_str)",
        "print(parsed['amount'])   # 75000.0",
        "",
        "# requests library does this automatically",
        "response = requests.get('https://api.fraudsystem.com/transactions/TXN-9983')",
        "data = response.json()   # Already a Python dict!",
    ])

    story += H2("2.8 Cookies and Sessions")
    story += P("While REST APIs typically use tokens (JWT) rather than cookies, it's important to understand both concepts.")
    story += P("<b>Cookies</b> are small pieces of data stored by the browser. They are automatically sent with every request to the same domain. Traditional web apps use session cookies to maintain login state.")
    story += P("<b>Sessions</b> store user state on the <i>server side</i>. The server creates a session ID and sends it to the client as a cookie. On subsequent requests, the client sends the cookie back and the server retrieves the session data.")
    story += P("<b>Why REST APIs usually avoid cookies and sessions:</b> REST is stateless — each request should carry all the information needed to process it. JWTs (JSON Web Tokens) embed user identity inside the token itself, making sessions unnecessary.")
    story += warn("Never store sensitive fraud data, API keys, or authentication tokens in cookies without the Secure, HttpOnly, and SameSite flags. Failure to do so can expose your system to XSS and CSRF attacks.")
    story += SP()

    story += summary_box([
        "HTTP defines seven main methods: GET (read), POST (create), PUT (replace), PATCH (partial update), DELETE (remove), OPTIONS (CORS check), HEAD (headers only).",
        "Status codes in the 2xx range mean success; 4xx means client error; 5xx means server error.",
        "Request headers carry metadata including Authorization tokens and Content-Type.",
        "Query parameters filter collections; path parameters identify specific resources.",
        "JSON is the universal data format for modern REST APIs.",
        "REST APIs favour stateless JWT authentication over cookies and sessions.",
    ])
    story += exercise_box("Chapter 2 Exercises", [
        "Write a Python script using the 'requests' library that makes a GET call to the free JSONPlaceholder API (jsonplaceholder.typicode.com/posts) and prints the first post's title.",
        "Describe what HTTP status codes 200, 201, 400, 401, 403, 404, 422, and 500 mean in the context of a fraud detection API.",
        "Design the URL structure for a fraud API that allows: listing all transactions, retrieving one transaction by ID, and retrieving all transactions for a specific customer.",
        "Create a JSON object representing a mobile money transaction that would be submitted to a fraud detection API. Include all relevant fields a fraud model would need.",
        "Explain the difference between query parameters and path parameters with two examples each from a banking API.",
    ])
    story += PBR()

    # ═══════════════════════════════════════════════
    # CHAPTER 3 — REST Architecture
    # ═══════════════════════════════════════════════
    story += chapter_header("3", "REST Architecture",
        "The six principles that define how well-designed APIs are built")

    story += H2("3.1 What Is REST?")
    story += P("REST stands for <b>Representational State Transfer</b>. It was defined in the year 2000 by Roy Fielding in his doctoral dissertation. REST is not a protocol or a standard — it is an <b>architectural style</b>, a set of guidelines for building networked applications.")
    story += P("A web service that follows REST principles is called a <b>RESTful API</b>. FastAPI, Django REST Framework, Flask, and Express.js all help you build RESTful APIs.")
    story += definition_box("REST", "An architectural style for distributed hypermedia systems that defines a set of constraints for how components should interact. Systems that follow all REST constraints are called RESTful.")

    story += H2("3.2 The Six REST Principles")

    story += H3("1. Stateless Communication")
    story += P("Every HTTP request from a client to a server must contain all information needed to process the request. The server must not store any session state about the client.")
    story += P("<b>Why this matters for fraud detection:</b> A fraud API may receive thousands of requests per second from hundreds of different clients. If the server had to maintain session state for all of them, it would run out of memory quickly. Stateless design allows horizontal scaling — you can add more servers and every server can handle any request.")
    story += ascii_diagram([
        "  WITHOUT stateless (BAD - sessions):",
        "  Request 1: Login -------> Server stores 'user=John, step=1'",
        "  Request 2: Submit data -> Server recalls 'user=John, step=1' -> BAD!",
        "  If server restarts, session is lost.",
        "",
        "  WITH stateless (GOOD - JWT):",
        "  Request 1: Login -------> Server returns JWT token (contains user info)",
        "  Request 2: Submit data + JWT -> Server reads JWT directly -> GOOD!",
        "  No server-side state needed.",
    ])

    story += H3("2. Client-Server Separation")
    story += P("The client and server are independent. The client handles the user interface; the server handles data storage and business logic. They can evolve independently as long as the API contract (endpoint design) does not change.")
    story += P("<b>Real-world example:</b> A bank's fraud detection API can be updated to use a new ML model without touching any of the mobile app code — as long as the request/response format stays the same.")

    story += H3("3. Cacheable")
    story += P("Responses must define themselves as cacheable or non-cacheable. If a response is cacheable, clients can reuse the data for subsequent requests, reducing server load and improving performance.")
    story += P("<b>Fraud detection context:</b> A list of high-risk merchant categories can be cached for 1 hour. Live fraud scores must never be cached — they must always be freshly calculated.")

    story += H3("4. Uniform Interface")
    story += P("All REST APIs must follow a consistent, uniform way of interacting with resources. This simplifies the architecture and makes APIs easier to understand. It consists of four sub-constraints:")
    story += B("<b>Resource identification in requests</b> — Each resource has a unique URI (e.g., /transactions/TXN-9983)")
    story += B("<b>Resource manipulation through representations</b> — Clients interact with JSON representations of resources, not the database directly")
    story += B("<b>Self-descriptive messages</b> — Each request contains all information needed to process it (method, headers, body)")
    story += B("<b>Hypermedia as the engine of application state (HATEOAS)</b> — Responses include links to related actions")

    story += H3("5. Layered System")
    story += P("The client should not need to know whether it is communicating directly with the final server or with an intermediary (load balancer, cache, API gateway). This enables scalable architectures.")
    story += ascii_diagram([
        "  Mobile App -> API Gateway -> Load Balancer -> FastAPI Server -> Database",
        "                    |                               |",
        "              Rate Limiting                  ML Fraud Model",
        "              Authentication                 Transaction DB",
        "              SSL Termination",
    ])

    story += H3("6. Code on Demand (Optional)")
    story += P("Servers can extend client functionality by sending executable code (e.g., JavaScript). This is the only optional REST constraint. Most REST APIs do not use this.")

    story += H2("3.3 Resources and Endpoints")
    story += P("In REST, everything is a <b>resource</b>. A resource is any concept that can be identified, named, and represented — a customer, a transaction, a fraud report, or a risk score.")
    story += P("An <b>endpoint</b> is the specific URL where a resource can be accessed. REST endpoints are designed around <b>nouns</b> (resources), not verbs (actions).")
    story += two_col_table(
        ["BAD (verb-based)", "GOOD (noun-based / RESTful)"],
        [
            ["/getTransaction", "/transactions/{id}"],
            ["/createTransaction", "/transactions  (POST)"],
            ["/deleteTransaction", "/transactions/{id}  (DELETE)"],
            ["/flagCustomerAsRisky", "/customers/{id}/risk-profile  (PATCH)"],
            ["/runFraudCheck", "/fraud-scores  (POST)"],
        ],
        [7.5*cm, 8*cm]
    )

    story += H2("3.4 URI Design Best Practices")
    story += P("A URI (Uniform Resource Identifier) is the address of a resource. Well-designed URIs are:")
    story += B("Lowercase: /transactions not /Transactions")
    story += B("Hyphen-separated words: /fraud-reports not /fraud_reports or /fraudReports")
    story += B("Plural for collections: /transactions not /transaction")
    story += B("Hierarchical for nested resources: /customers/{id}/transactions")
    story += B("Version-prefixed: /v1/transactions or /api/v1/transactions")
    story += B("Never contain verbs: /transactions not /get-transactions")
    story += code_block([
        "# Good REST URI examples for a fraud detection API",
        "",
        "GET  /v1/transactions              # Get all transactions",
        "POST /v1/transactions              # Submit new transaction for fraud check",
        "GET  /v1/transactions/{id}         # Get specific transaction",
        "PATCH /v1/transactions/{id}        # Update transaction status",
        "DELETE /v1/transactions/{id}       # Delete transaction",
        "",
        "GET  /v1/customers/{id}/transactions    # All transactions for customer",
        "GET  /v1/customers/{id}/fraud-score     # Get customer's risk score",
        "POST /v1/customers/{id}/flags           # Flag a customer as high-risk",
        "",
        "GET  /v1/merchants/{id}/risk-profile    # Merchant risk assessment",
        "GET  /v1/reports/daily-summary          # Aggregate fraud stats",
    ])

    story += H2("3.5 CRUD Operations Mapped to HTTP")
    story += P("CRUD stands for <b>Create, Read, Update, Delete</b> — the four fundamental operations on data. Every REST API maps these to HTTP methods:")
    story += two_col_table(
        ["CRUD Operation", "HTTP Method", "Example Endpoint", "Fraud System Use Case"],
        [
            ["Create", "POST", "POST /transactions", "Submit a new transaction for fraud analysis"],
            ["Read (all)", "GET", "GET /transactions", "Retrieve all flagged transactions today"],
            ["Read (one)", "GET", "GET /transactions/{id}", "View details of a specific fraud case"],
            ["Update (full)", "PUT", "PUT /customers/{id}", "Replace entire customer risk profile"],
            ["Update (partial)", "PATCH", "PATCH /transactions/{id}", "Update only the fraud flag of a transaction"],
            ["Delete", "DELETE", "DELETE /transactions/{id}", "Remove a test transaction from the system"],
        ],
        [2.8*cm, 2.8*cm, 4.5*cm, 5.4*cm]
    )

    story += H2("3.6 Idempotency")
    story += P("An operation is <b>idempotent</b> if calling it multiple times produces the same result as calling it once. This is critical for distributed systems where network failures can cause requests to be retried.")
    story += two_col_table(
        ["Method", "Idempotent?", "Why?"],
        [
            ["GET", "Yes", "Reading data never changes it"],
            ["PUT", "Yes", "Replacing a resource with the same data always produces the same state"],
            ["PATCH", "Usually", "Depends on implementation — setting a field to a value is idempotent"],
            ["DELETE", "Yes", "Deleting something that is already deleted has the same end state"],
            ["POST", "No", "Creating a new resource each time produces a new resource"],
        ],
        [3*cm, 3*cm, 9.5*cm]
    )
    story += note("In a fraud detection system, if a transaction submission (POST) fails due to a network error, the client should not blindly retry — this could create duplicate transactions. A proper system uses idempotency keys or checks for duplicate transaction IDs.")

    story += summary_box([
        "REST is an architectural style, not a protocol — it defines guidelines for building scalable, maintainable APIs.",
        "Statelessness is the most important REST constraint — each request must be self-contained.",
        "Resources are nouns; HTTP methods express actions. Never put verbs in URLs.",
        "URI design should be lowercase, plural, hyphenated, and hierarchical.",
        "CRUD maps to POST (Create), GET (Read), PUT/PATCH (Update), DELETE (Delete).",
        "Idempotency ensures safe retries — GET, PUT, and DELETE are idempotent; POST is not.",
    ])
    story += PBR()

    # ═══════════════════════════════════════════════
    # CHAPTER 4 — Python Review
    # ═══════════════════════════════════════════════
    story += chapter_header("4", "Python Review for API Development",
        "Essential Python concepts you must master before building APIs with FastAPI")

    story += H2("4.1 Functions in Python")
    story += P("Functions are the building blocks of any Python application. In FastAPI, every API endpoint is a Python function.")
    story += code_block([
        "# Basic function definition",
        "def calculate_fraud_score(amount: float, is_new_merchant: bool) -> float:",
        "    '''",
        "    Calculate a simple rule-based fraud score.",
        "    Returns a float between 0.0 (safe) and 1.0 (definite fraud).",
        "    '''",
        "    score = 0.0",
        "",
        "    # Large amounts are suspicious",
        "    if amount > 50000:",
        "        score += 0.4",
        "",
        "    # New merchants add risk",
        "    if is_new_merchant:",
        "        score += 0.3",
        "",
        "    # Cap score at 1.0",
        "    return min(score, 1.0)",
        "",
        "# Call the function",
        "score = calculate_fraud_score(75000.00, True)",
        "print(f'Fraud score: {score}')   # Fraud score: 0.7",
    ])

    story += H3("Default and Keyword Arguments")
    story += code_block([
        "def flag_transaction(",
        "    transaction_id: str,",
        "    reason: str = 'Manual review',   # Default value",
        "    notify_customer: bool = False,    # Default value",
        ") -> dict:",
        "    return {",
        "        'id': transaction_id,",
        "        'flagged': True,",
        "        'reason': reason,",
        "        'customer_notified': notify_customer",
        "    }",
        "",
        "# Positional argument",
        "flag_transaction('TXN-001')",
        "",
        "# Keyword arguments — order doesn't matter",
        "flag_transaction(transaction_id='TXN-002', notify_customer=True, reason='Unusual pattern')",
    ])

    story += H2("4.2 Classes and Object-Oriented Programming")
    story += P("FastAPI uses classes extensively for data models, dependencies, and more. Understanding classes is essential.")
    story += code_block([
        "from datetime import datetime",
        "",
        "class Transaction:",
        "    '''Represents a financial transaction in our fraud system.'''",
        "",
        "    # Class variable — shared by all instances",
        "    total_count = 0",
        "",
        "    def __init__(self, transaction_id: str, amount: float, customer_id: str):",
        "        # Instance variables — unique to each transaction",
        "        self.transaction_id = transaction_id",
        "        self.amount = amount",
        "        self.customer_id = customer_id",
        "        self.timestamp = datetime.now()",
        "        self.flagged = False",
        "        self.fraud_score = 0.0",
        "        Transaction.total_count += 1   # Update class variable",
        "",
        "    def flag(self, reason: str) -> None:",
        "        '''Mark this transaction as potentially fraudulent.'''",
        "        self.flagged = True",
        "        self.flag_reason = reason",
        "",
        "    def is_high_risk(self) -> bool:",
        "        '''Return True if fraud score exceeds the risk threshold.'''",
        "        return self.fraud_score >= 0.7",
        "",
        "    def __repr__(self) -> str:",
        "        '''String representation for debugging.'''",
        "        return f'Transaction({self.transaction_id}, {self.amount} KES, flagged={self.flagged})'",
        "",
        "# Create instances",
        "txn1 = Transaction('TXN-001', 75000.00, 'KE-002341')",
        "txn2 = Transaction('TXN-002', 500.00, 'KE-001122')",
        "",
        "txn1.fraud_score = 0.89",
        "print(txn1.is_high_risk())    # True",
        "print(Transaction.total_count)  # 2",
    ])

    story += H2("4.3 Type Hints")
    story += P("Type hints are annotations that tell readers (and tools) what type a variable, parameter, or return value should be. FastAPI <b>requires</b> type hints — it uses them to validate request data and generate documentation automatically.")
    story += code_block([
        "from typing import Optional, List, Dict, Union",
        "",
        "# Basic type hints",
        "customer_id: str = 'KE-002341'",
        "amount: float = 75000.00",
        "is_flagged: bool = False",
        "transaction_count: int = 0",
        "",
        "# Function with type hints",
        "def get_fraud_score(transaction_id: str) -> float:",
        "    ...",
        "",
        "# Optional means the value could be None",
        "def get_transaction(txn_id: str, reviewer: Optional[str] = None) -> dict:",
        "    ...",
        "",
        "# List of strings",
        "def get_flags(txn_id: str) -> List[str]:",
        "    return ['unusual_amount', 'new_merchant']",
        "",
        "# Dictionary with str keys and float values",
        "def get_risk_scores(customer_ids: List[str]) -> Dict[str, float]:",
        "    ...",
        "",
        "# Union means it can be one type OR another",
        "def parse_amount(value: Union[str, float]) -> float:",
        "    return float(value)",
    ])

    story += H2("4.4 Exception Handling")
    story += P("Proper exception handling is critical in production APIs. A well-handled exception returns a meaningful error response; a poorly handled one crashes the entire server.")
    story += code_block([
        "class TransactionNotFoundError(Exception):",
        "    '''Raised when a transaction ID does not exist in the database.'''",
        "    pass",
        "",
        "class FraudModelError(Exception):",
        "    '''Raised when the ML model fails to produce a score.'''",
        "    pass",
        "",
        "def get_fraud_prediction(transaction_id: str) -> dict:",
        "    try:",
        "        # Try to fetch transaction from database",
        "        txn = database.get(transaction_id)",
        "        if txn is None:",
        "            raise TransactionNotFoundError(f'Transaction {transaction_id} not found')",
        "",
        "        # Try to get ML prediction",
        "        score = ml_model.predict(txn)",
        "        return {'fraud_score': score, 'transaction_id': transaction_id}",
        "",
        "    except TransactionNotFoundError as e:",
        "        # Re-raise — the API layer will handle this",
        "        raise",
        "",
        "    except Exception as e:",
        "        # Catch-all — wrap in our custom error",
        "        raise FraudModelError(f'Model prediction failed: {str(e)}') from e",
        "",
        "    finally:",
        "        # This always runs — use for cleanup",
        "        print(f'Processed request for {transaction_id}')",
    ])

    story += H2("4.5 Virtual Environments and pip")
    story += P("A virtual environment is an isolated Python environment for your project. It prevents package version conflicts between different projects.")
    story += code_block([
        "# Create a virtual environment",
        "python -m venv fraud_api_env",
        "",
        "# Activate it (Linux/Mac)",
        "source fraud_api_env/bin/activate",
        "",
        "# Activate it (Windows)",
        "fraud_api_env\\Scripts\\activate",
        "",
        "# Install packages",
        "pip install fastapi uvicorn sqlalchemy pydantic",
        "",
        "# Save dependencies to a file",
        "pip freeze > requirements.txt",
        "",
        "# Install from requirements file (for new environments)",
        "pip install -r requirements.txt",
        "",
        "# Deactivate the virtual environment",
        "deactivate",
    ])
    story += tip("Always create a virtual environment for every project. This is standard professional practice and prevents the dreaded 'it works on my machine but not on the server' problem.")

    story += H2("4.6 Modules and Packages")
    story += code_block([
        "# fraud_utils.py — a module",
        "",
        "RISK_THRESHOLDS = {",
        "    'LOW': 0.3,",
        "    'MEDIUM': 0.6,",
        "    'HIGH': 0.8,",
        "    'CRITICAL': 0.95",
        "}",
        "",
        "def get_risk_level(score: float) -> str:",
        "    '''Map a fraud score to a human-readable risk level.'''",
        "    if score >= RISK_THRESHOLDS['CRITICAL']:",
        "        return 'CRITICAL'",
        "    elif score >= RISK_THRESHOLDS['HIGH']:",
        "        return 'HIGH'",
        "    elif score >= RISK_THRESHOLDS['MEDIUM']:",
        "        return 'MEDIUM'",
        "    else:",
        "        return 'LOW'",
        "",
        "# In another file, import and use this module:",
        "# from fraud_utils import get_risk_level",
        "# level = get_risk_level(0.89)   # 'HIGH'",
    ])

    story += summary_box([
        "FastAPI is built on Python — mastering functions, classes, type hints, and exceptions is non-negotiable.",
        "Type hints are required by FastAPI for automatic request validation and documentation generation.",
        "Always use virtual environments to isolate project dependencies.",
        "Custom exceptions make error handling clear and allow the API layer to return appropriate HTTP error codes.",
        "Modules allow you to organise code into separate files, making large FastAPI projects maintainable.",
    ])
    story += PBR()

    # ═══════════════════════════════════════════════
    # CHAPTER 5 — Introduction to FastAPI
    # ═══════════════════════════════════════════════
    story += chapter_header("5", "Introduction to FastAPI",
        "Your first FastAPI application — from installation to running a live server")

    story += H2("5.1 What Is FastAPI?")
    story += P("FastAPI is a modern, high-performance Python web framework for building APIs. Created by Sebastián Ramírez (tiangolo) and first released in 2018, it has quickly become one of the most popular Python frameworks for API development.")
    story += P("Key features of FastAPI:")
    story += B("<b>Extremely fast</b> — On par with Node.js and Go, thanks to async support and Starlette")
    story += B("<b>Automatic documentation</b> — Generates Swagger UI and ReDoc automatically from your code")
    story += B("<b>Type safety</b> — Uses Python type hints for automatic validation via Pydantic")
    story += B("<b>Standards-based</b> — Built on OpenAPI and JSON Schema")
    story += B("<b>Production-ready</b> — Used by companies including Microsoft, Uber, and Netflix")
    story += SP()
    story += two_col_table(
        ["Framework", "Speed", "Auto Docs", "Validation", "Learning Curve"],
        [
            ["FastAPI", "Very High", "Yes (built-in)", "Automatic (Pydantic)", "Low-Medium"],
            ["Flask", "Medium", "Extension needed", "Manual", "Low"],
            ["Django REST", "Medium", "Extension needed", "Serializers", "Medium-High"],
            ["Express (Node)", "High", "Extension needed", "Manual", "Medium"],
        ],
        [3.5*cm, 2.5*cm, 3*cm, 3.5*cm, 3*cm]
    )

    story += H2("5.2 Installation")
    story += code_block([
        "# Step 1: Create and activate virtual environment",
        "python -m venv fraud_api_env",
        "source fraud_api_env/bin/activate   # Linux/Mac",
        "# fraud_api_env\\Scripts\\activate   # Windows",
        "",
        "# Step 2: Install FastAPI with all optional dependencies",
        "pip install 'fastapi[all]'",
        "# This installs: fastapi, uvicorn, pydantic, httpx, and more",
        "",
        "# OR install individually",
        "pip install fastapi",
        "pip install 'uvicorn[standard]'",
        "",
        "# Verify installation",
        "python -c 'import fastapi; print(fastapi.__version__)'",
    ])
    story += P("<b>Uvicorn</b> is an ASGI (Asynchronous Server Gateway Interface) web server that runs your FastAPI application. Think of it as the engine that actually listens for HTTP connections and hands them to FastAPI.")

    story += H2("5.3 Your First FastAPI Application")
    story += P("Let's create the simplest possible FastAPI app — a single endpoint that returns a welcome message.")
    story += code_block([
        "# main.py — Our first FastAPI application",
        "from fastapi import FastAPI   # Import the FastAPI class",
        "",
        "# Create the FastAPI application instance",
        "# This 'app' object is the central object of our API",
        "app = FastAPI(",
        "    title='Fraud Detection API',",
        "    description='An API for detecting fraudulent transactions in real time',",
        "    version='1.0.0'",
        ")",
        "",
        "# Define a route — a URL path and the function that handles it",
        "@app.get('/')   # This is a 'decorator' — it registers the function as a GET endpoint",
        "def read_root():",
        "    '''Return a welcome message — this becomes the API documentation description.'''",
        "    return {'message': 'Welcome to the Fraud Detection API', 'status': 'online'}",
        "",
        "# A second endpoint — health check (common in production APIs)",
        "@app.get('/health')",
        "def health_check():",
        "    return {'status': 'healthy', 'version': '1.0.0'}",
    ])

    story += H2("5.4 Running the Server")
    story += code_block([
        "# Run the server (from terminal, in the same directory as main.py)",
        "uvicorn main:app --reload",
        "#       |    |     |",
        "#       |    |     +-- Auto-reload when code changes (use in development only)",
        "#       |    +-------- The 'app' variable inside main.py",
        "#       +------------- The filename 'main.py' (without .py)",
        "",
        "# You should see output like:",
        "# INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)",
        "# INFO:     Started reloader process",
        "",
        "# Optional: specify host and port",
        "uvicorn main:app --reload --host 0.0.0.0 --port 8080",
    ])
    story += P("Open your browser and visit <b>http://127.0.0.1:8000</b> — you should see the JSON response from your root endpoint.")

    story += H2("5.5 Automatic Documentation")
    story += P("This is one of FastAPI's most powerful features. Without writing a single line of documentation code, FastAPI generates two interactive documentation UIs for you:")
    story += B("<b>Swagger UI</b> — Available at http://127.0.0.1:8000/docs — Interactive documentation where you can test endpoints directly from the browser")
    story += B("<b>ReDoc</b> — Available at http://127.0.0.1:8000/redoc — Clean, readable documentation suitable for sharing with other developers or clients")
    story += B("<b>OpenAPI JSON</b> — Available at http://127.0.0.1:8000/openapi.json — The raw OpenAPI specification file")
    story += SP()
    story += tip("Show the /docs URL to stakeholders and clients — it's your API's live, interactive specification. Banks and enterprise clients often require OpenAPI documentation before integrating with your API.")
    story += note("Swagger UI allows you to try every endpoint directly in the browser, including sending request bodies and viewing responses. This is invaluable for testing and debugging during development.")

    story += H2("5.6 Project Structure")
    story += P("As your API grows, you'll need to organise your code into multiple files. Here's the recommended project structure for a production FastAPI application:")
    story += code_block([
        "fraud_detection_api/",
        "├── main.py                    # Entry point — creates FastAPI app",
        "├── requirements.txt           # Python dependencies",
        "├── .env                       # Environment variables (secrets — never commit!)",
        "├── .gitignore                 # Files Git should ignore",
        "├── Dockerfile                 # For containerisation",
        "│",
        "├── app/",
        "│   ├── __init__.py",
        "│   ├── config.py              # Settings and configuration",
        "│   ├── database.py            # Database connection",
        "│   │",
        "│   ├── models/                # SQLAlchemy database models",
        "│   │   ├── __init__.py",
        "│   │   ├── transaction.py",
        "│   │   └── customer.py",
        "│   │",
        "│   ├── schemas/               # Pydantic validation schemas",
        "│   │   ├── __init__.py",
        "│   │   ├── transaction.py",
        "│   │   └── customer.py",
        "│   │",
        "│   ├── routers/               # API route handlers",
        "│   │   ├── __init__.py",
        "│   │   ├── transactions.py",
        "│   │   ├── customers.py",
        "│   │   └── auth.py",
        "│   │",
        "│   ├── services/              # Business logic",
        "│   │   ├── fraud_detector.py",
        "│   │   └── notification.py",
        "│   │",
        "│   └── dependencies.py        # Shared dependencies (auth, DB sessions)",
        "│",
        "└── tests/                     # Test files",
        "    ├── __init__.py",
        "    ├── test_transactions.py",
        "    └── test_auth.py",
    ])

    story += summary_box([
        "FastAPI is a modern, high-performance Python framework that generates API documentation automatically.",
        "Install FastAPI with 'pip install fastapi[all]' and run with 'uvicorn main:app --reload'.",
        "Every endpoint is a Python function decorated with @app.get(), @app.post(), etc.",
        "Swagger UI (/docs) and ReDoc (/redoc) are generated automatically from your code.",
        "Organise larger projects into routers, models, schemas, and services directories.",
    ])
    story += exercise_box("Chapter 5 Exercises", [
        "Create a new FastAPI project with a virtual environment. Write an app with three endpoints: root (/), health check (/health), and a greeting (/greet/{name}) that returns 'Hello, {name}!'.",
        "Navigate to /docs and test all three of your endpoints from the Swagger UI interface.",
        "Add meaningful title, description, and version metadata to your FastAPI app instance. Observe how this changes the /docs page.",
        "Add an endpoint /fraud-system/info that returns a JSON object with the system name, supported currencies, ML model version, and contact email.",
        "Look at the OpenAPI JSON at /openapi.json and identify where your endpoint descriptions appear.",
    ])
    story += PBR()

    # ═══════════════════════════════════════════════
    # CHAPTER 6 — Building CRUD Endpoints
    # ═══════════════════════════════════════════════
    story += chapter_header("6", "Building CRUD Endpoints",
        "Implementing GET, POST, PUT, PATCH, and DELETE endpoints in FastAPI")

    story += H2("6.1 GET Endpoints")
    story += P("GET endpoints retrieve data. FastAPI makes it simple to define them using the @app.get() decorator.")
    story += code_block([
        "from fastapi import FastAPI",
        "from typing import List, Optional",
        "",
        "app = FastAPI(title='Fraud Detection API')",
        "",
        "# In-memory store (we'll use a real database in Chapter 12)",
        "transactions_db = [",
        "    {'id': 'TXN-001', 'amount': 75000.0, 'currency': 'KES', 'flagged': True},",
        "    {'id': 'TXN-002', 'amount': 1200.0, 'currency': 'KES', 'flagged': False},",
        "    {'id': 'TXN-003', 'amount': 250000.0, 'currency': 'KES', 'flagged': True},",
        "]",
        "",
        "# GET /transactions — return all transactions",
        "@app.get('/transactions')",
        "def get_all_transactions():",
        "    '''Retrieve all transactions from the system.'''",
        "    return transactions_db",
        "",
        "# GET /transactions/{transaction_id} — return one transaction",
        "@app.get('/transactions/{transaction_id}')",
        "def get_transaction(transaction_id: str):",
        "    '''",
        "    Retrieve a single transaction by its ID.",
        "    The {transaction_id} in the path becomes a function parameter.",
        "    '''",
        "    for txn in transactions_db:",
        "        if txn['id'] == transaction_id:",
        "            return txn",
        "    # We'll improve error handling in Chapter 13",
        "    return {'error': 'Transaction not found'}",
    ])

    story += H2("6.2 POST Endpoints")
    story += P("POST endpoints create new resources. We send data in the request body as JSON.")
    story += code_block([
        "from fastapi import FastAPI",
        "from pydantic import BaseModel  # For request body validation (Chapter 7)",
        "from typing import Optional",
        "import uuid",
        "",
        "app = FastAPI()",
        "",
        "# Define what data we expect in the request body",
        "class TransactionCreate(BaseModel):",
        "    amount: float",
        "    currency: str = 'KES'",
        "    customer_id: str",
        "    merchant: str",
        "    location: Optional[str] = None",
        "",
        "transactions_db = {}",
        "",
        "@app.post('/transactions', status_code=201)",
        "def create_transaction(transaction: TransactionCreate):",
        "    '''",
        "    Submit a new transaction for fraud analysis.",
        "    Returns the transaction with a generated ID and fraud score.",
        "    '''",
        "    # Generate a unique transaction ID",
        "    txn_id = f'TXN-{str(uuid.uuid4())[:8].upper()}'",
        "",
        "    # Simple rule-based fraud scoring (replaced by ML in Chapter 20)",
        "    score = 0.0",
        "    if transaction.amount > 50000:",
        "        score += 0.5",
        "    if transaction.currency != 'KES':",
        "        score += 0.2",
        "",
        "    # Build the full transaction record",
        "    new_txn = {",
        "        'id': txn_id,",
        "        'amount': transaction.amount,",
        "        'currency': transaction.currency,",
        "        'customer_id': transaction.customer_id,",
        "        'merchant': transaction.merchant,",
        "        'location': transaction.location,",
        "        'fraud_score': round(score, 2),",
        "        'flagged': score >= 0.5",
        "    }",
        "    transactions_db[txn_id] = new_txn",
        "    return new_txn",
    ])

    story += H2("6.3 PUT and PATCH Endpoints")
    story += code_block([
        "# PUT — replace an entire transaction record",
        "@app.put('/transactions/{transaction_id}')",
        "def replace_transaction(transaction_id: str, transaction: TransactionCreate):",
        "    if transaction_id not in transactions_db:",
        "        return {'error': 'Not found'}",
        "    transactions_db[transaction_id].update({",
        "        'amount': transaction.amount,",
        "        'currency': transaction.currency,",
        "        'customer_id': transaction.customer_id,",
        "        'merchant': transaction.merchant,",
        "    })",
        "    return transactions_db[transaction_id]",
        "",
        "# PATCH — update only specific fields",
        "class TransactionUpdate(BaseModel):",
        "    flagged: Optional[bool] = None",
        "    fraud_score: Optional[float] = None",
        "    reviewed_by: Optional[str] = None",
        "",
        "@app.patch('/transactions/{transaction_id}')",
        "def update_transaction(transaction_id: str, update: TransactionUpdate):",
        "    if transaction_id not in transactions_db:",
        "        return {'error': 'Not found'}",
        "    # Only update fields that were actually provided",
        "    update_data = update.dict(exclude_none=True)   # Skip None values",
        "    transactions_db[transaction_id].update(update_data)",
        "    return transactions_db[transaction_id]",
    ])

    story += H2("6.4 DELETE Endpoint")
    story += code_block([
        "from fastapi import Response",
        "",
        "@app.delete('/transactions/{transaction_id}', status_code=204)",
        "def delete_transaction(transaction_id: str, response: Response):",
        "    '''",
        "    Delete a transaction by ID.",
        "    Returns 204 No Content on success (standard REST practice).",
        "    '''",
        "    if transaction_id not in transactions_db:",
        "        response.status_code = 404",
        "        return {'error': 'Transaction not found'}",
        "",
        "    del transactions_db[transaction_id]",
        "    # 204 means we return no body",
    ])

    story += summary_box([
        "Use @app.get() for reading data, @app.post() for creating, @app.put() for full replacement, @app.patch() for partial updates, and @app.delete() for removal.",
        "Path parameters in the URL (e.g., {transaction_id}) automatically become function parameters.",
        "Always set the correct status_code in the decorator — 201 for created resources, 204 for deleted resources.",
        "PATCH only updates provided fields by using .dict(exclude_none=True) on the Pydantic model.",
    ])
    story += PBR()

    # ═══════════════════════════════════════════════
    # CHAPTER 7 — Pydantic Models
    # ═══════════════════════════════════════════════
    story += chapter_header("7", "Pydantic Models and Data Validation",
        "Ensuring every byte that enters or leaves your API is correct")

    story += H2("7.1 What Is Pydantic?")
    story += P("Pydantic is a Python library that provides <b>data validation and settings management using Python type annotations</b>. FastAPI is built on top of Pydantic — it uses Pydantic models to validate every incoming request automatically.")
    story += P("When a client sends data to your API, Pydantic:")
    story += B("Validates that all required fields are present")
    story += B("Validates that each field is the correct type")
    story += B("Converts data where possible (e.g., '75000' string to 75000.0 float)")
    story += B("Returns a detailed 422 error if validation fails, listing every problem")

    story += H2("7.2 Defining Pydantic Models")
    story += code_block([
        "from pydantic import BaseModel, Field, validator",
        "from typing import Optional, List",
        "from datetime import datetime",
        "from enum import Enum",
        "",
        "# Use Enum for fields with limited valid values",
        "class Currency(str, Enum):",
        "    KES = 'KES'   # Kenyan Shilling",
        "    USD = 'USD'   # US Dollar",
        "    EUR = 'EUR'   # Euro",
        "    GBP = 'GBP'   # British Pound",
        "",
        "class RiskLevel(str, Enum):",
        "    LOW = 'LOW'",
        "    MEDIUM = 'MEDIUM'",
        "    HIGH = 'HIGH'",
        "    CRITICAL = 'CRITICAL'",
        "",
        "# The main transaction request model",
        "class TransactionCreate(BaseModel):",
        "    # Field() adds extra validation and documentation",
        "    amount: float = Field(",
        "        ...,                    # '...' means required (no default)",
        "        gt=0,                   # Must be greater than 0",
        "        lt=10_000_000,          # Must be less than 10 million",
        "        description='Transaction amount in the specified currency',",
        "        example=75000.00",
        "    )",
        "    currency: Currency = Field(default=Currency.KES, description='ISO 4217 currency code')",
        "    customer_id: str = Field(..., min_length=5, max_length=20, example='KE-002341')",
        "    merchant: str = Field(..., min_length=2, max_length=100)",
        "    location: Optional[str] = Field(None, max_length=200)",
        "    payment_method: str = Field('CARD', pattern='^(CARD|MOBILE|CASH|BANK_TRANSFER)$')",
        "",
        "    class Config:",
        "        # Show example in /docs",
        "        schema_extra = {",
        "            'example': {",
        "                'amount': 75000.00,",
        "                'currency': 'KES',",
        "                'customer_id': 'KE-002341',",
        "                'merchant': 'Electronics Hub Nairobi',",
        "                'location': 'Westlands, Nairobi',",
        "                'payment_method': 'CARD'",
        "            }",
        "        }",
    ])

    story += H2("7.3 Response Models")
    story += P("Response models define what the API returns to the client. By specifying a response model, FastAPI automatically filters out any fields that shouldn't be exposed (like internal database IDs or passwords).")
    story += code_block([
        "# Different models for different purposes",
        "",
        "# What we store internally (includes sensitive system fields)",
        "class TransactionInternal(BaseModel):",
        "    id: str",
        "    amount: float",
        "    currency: Currency",
        "    customer_id: str",
        "    merchant: str",
        "    fraud_score: float",
        "    flagged: bool",
        "    ml_model_version: str    # Internal — don't expose",
        "    raw_features: dict       # Internal — never expose",
        "    timestamp: datetime",
        "",
        "# What we return to the API client (safe subset)",
        "class TransactionResponse(BaseModel):",
        "    id: str",
        "    amount: float",
        "    currency: Currency",
        "    fraud_score: float",
        "    risk_level: RiskLevel",
        "    flagged: bool",
        "    timestamp: datetime",
        "",
        "    class Config:",
        "        orm_mode = True   # Allows working with SQLAlchemy models",
        "",
        "# Using response_model in the endpoint",
        "@app.post('/transactions', response_model=TransactionResponse, status_code=201)",
        "def create_transaction(transaction: TransactionCreate):",
        "    # ... process transaction ...",
        "    # Even if we return a dict with extra fields,",
        "    # FastAPI will filter it to match TransactionResponse",
        "    pass",
    ])

    story += H2("7.4 Custom Validators")
    story += P("Sometimes standard field constraints aren't enough. Pydantic allows you to write custom validation functions.")
    story += code_block([
        "from pydantic import BaseModel, Field, validator, root_validator",
        "",
        "class TransactionCreate(BaseModel):",
        "    amount: float = Field(..., gt=0)",
        "    currency: str",
        "    sender_account: str",
        "    receiver_account: str",
        "",
        "    @validator('currency')",
        "    def currency_must_be_valid(cls, v):",
        "        '''Validate that currency is a supported ISO code.'''",
        "        valid_currencies = {'KES', 'USD', 'EUR', 'GBP', 'TZS', 'UGX'}",
        "        if v.upper() not in valid_currencies:",
        "            raise ValueError(f'Currency {v} is not supported. Use: {valid_currencies}')",
        "        return v.upper()   # Normalise to uppercase",
        "",
        "    @validator('sender_account')",
        "    def account_format_valid(cls, v):",
        "        '''Validate Kenyan bank account format.'''",
        "        if not v.startswith(('KE', 'ACC')) or len(v) < 6:",
        "            raise ValueError('Account ID must start with KE or ACC and be at least 6 chars')",
        "        return v",
        "",
        "    @root_validator  # Runs after all individual validators",
        "    def sender_not_same_as_receiver(cls, values):",
        "        '''Business rule: cannot send money to yourself.'''",
        "        sender = values.get('sender_account')",
        "        receiver = values.get('receiver_account')",
        "        if sender and receiver and sender == receiver:",
        "            raise ValueError('Sender and receiver accounts cannot be the same')",
        "        return values",
    ])
    story += warn("Never trust client-provided data without validation. A fraudster could send negative amounts, impossible dates, or malformed IDs to exploit your system. Pydantic's validators are your first line of defence.")

    story += summary_box([
        "Pydantic models automatically validate all incoming request data and return 422 errors with detailed messages if validation fails.",
        "Use Field() to add constraints: gt, lt, min_length, max_length, pattern, description, example.",
        "Define separate Request and Response models — response models prevent accidental exposure of sensitive internal data.",
        "Use Enum classes to restrict fields to a specific set of valid values.",
        "Custom validators (@validator) allow you to encode complex business rules.",
        "orm_mode = True in the Config class is required when returning SQLAlchemy model objects.",
    ])
    story += PBR()

    # ═══════════════════════════════════════════════
    # CHAPTERS 8-10 — Parameters & Dependency Injection
    # ═══════════════════════════════════════════════
    story += chapter_header("8", "Path and Query Parameters",
        "Capturing data from the URL itself")

    story += H2("8.1 Path Parameters")
    story += P("Path parameters capture values directly from the URL path. They are defined using curly braces in the path string and automatically become function parameters with type validation.")
    story += code_block([
        "from fastapi import FastAPI, HTTPException",
        "from typing import Optional",
        "",
        "app = FastAPI()",
        "",
        "# Basic path parameter",
        "@app.get('/transactions/{transaction_id}')",
        "def get_transaction(transaction_id: str):  # Type hint validates and converts the value",
        "    return {'transaction_id': transaction_id}",
        "",
        "# Multiple path parameters",
        "@app.get('/customers/{customer_id}/transactions/{transaction_id}')",
        "def get_customer_transaction(customer_id: str, transaction_id: str):",
        "    return {'customer': customer_id, 'transaction': transaction_id}",
        "",
        "# Integer path parameter — FastAPI auto-converts and validates",
        "@app.get('/reports/{year}/{month}')",
        "def get_monthly_report(year: int, month: int):",
        "    if not 1 <= month <= 12:",
        "        raise HTTPException(status_code=400, detail='Month must be 1-12')",
        "    return {'year': year, 'month': month, 'report': 'fraud_summary'}",
    ])
    story += note("If you declare a path parameter as 'int' and the client sends a non-numeric value, FastAPI automatically returns a 422 error. No extra code needed!")

    story += H2("8.2 Query Parameters")
    story += P("Query parameters are added after a '?' in the URL. In FastAPI, any function parameter that is NOT a path parameter and NOT a Pydantic model is treated as a query parameter.")
    story += code_block([
        "from typing import Optional, List",
        "from enum import Enum",
        "",
        "class SortOrder(str, Enum):",
        "    asc = 'asc'",
        "    desc = 'desc'",
        "",
        "@app.get('/transactions')",
        "def list_transactions(",
        "    # Optional query params — have defaults so they're not required",
        "    page: int = 1,",
        "    limit: int = 20,",
        "    flagged_only: bool = False,",
        "    min_amount: Optional[float] = None,",
        "    max_amount: Optional[float] = None,",
        "    sort_by: str = 'timestamp',",
        "    order: SortOrder = SortOrder.desc,",
        "):",
        "    '''",
        "    GET /transactions?page=2&limit=10&flagged_only=true&min_amount=10000",
        "    All parameters are optional and have sensible defaults.",
        "    '''",
        "    results = fake_database  # Would query DB in real app",
        "",
        "    if flagged_only:",
        "        results = [t for t in results if t['flagged']]",
        "",
        "    if min_amount is not None:",
        "        results = [t for t in results if t['amount'] >= min_amount]",
        "",
        "    if max_amount is not None:",
        "        results = [t for t in results if t['amount'] <= max_amount]",
        "",
        "    # Pagination",
        "    start = (page - 1) * limit",
        "    end = start + limit",
        "",
        "    return {",
        "        'total': len(results),",
        "        'page': page,",
        "        'limit': limit,",
        "        'data': results[start:end]",
        "    }",
    ])
    story += PBR()

    # ═══════════════════════════════════════════════
    # CHAPTER 10 — Dependency Injection
    # ═══════════════════════════════════════════════
    story += chapter_header("10", "Dependency Injection",
        "Reusable, testable components for authentication, database connections, and more")

    story += H2("10.1 What Is Dependency Injection?")
    story += P("Dependency Injection (DI) is a design pattern where a component's dependencies are provided to it rather than created by it. In FastAPI, the DI system allows you to declare dependencies that will be automatically resolved and provided to your route functions.")
    story += P("Common use cases:")
    story += B("Provide a database session to every endpoint that needs one")
    story += B("Authenticate a user and inject the current user into protected endpoints")
    story += B("Rate limiting — check and decrement request quota before processing")
    story += B("Logging — log every request with shared context")
    story += code_block([
        "from fastapi import FastAPI, Depends, HTTPException, Header",
        "from typing import Optional",
        "",
        "app = FastAPI()",
        "",
        "# A simple dependency — validates the API key header",
        "async def verify_api_key(x_api_key: str = Header(...)):",
        "    '''",
        "    This function is a dependency.",
        "    FastAPI automatically extracts the X-Api-Key header and passes it here.",
        "    '''",
        "    valid_keys = {'fraud-api-key-prod-2024', 'fraud-api-key-staging-2024'}",
        "    if x_api_key not in valid_keys:",
        "        raise HTTPException(status_code=401, detail='Invalid API key')",
        "    return x_api_key   # Returned value is injected into the endpoint",
        "",
        "# Inject the dependency using Depends()",
        "@app.get('/transactions', dependencies=[Depends(verify_api_key)])",
        "def list_transactions():",
        "    return {'message': 'You are authenticated!'}",
        "",
        "# Alternative: inject return value into the function",
        "@app.get('/my-info')",
        "def get_my_info(api_key: str = Depends(verify_api_key)):",
        "    return {'your_api_key': api_key[:8] + '...', 'access': 'granted'}",
    ])

    story += H2("10.2 Database Session Dependency")
    story += P("The most common use of DI in FastAPI is providing database sessions. The dependency opens a session, yields it to the endpoint, and ensures it's always closed properly — even if an exception occurs.")
    story += code_block([
        "from sqlalchemy.orm import Session",
        "from database import SessionLocal   # We'll build this in Chapter 12",
        "",
        "def get_db():",
        "    '''",
        "    Dependency that provides a database session.",
        "    The 'yield' makes this a generator — code after yield runs after the endpoint.",
        "    '''",
        "    db = SessionLocal()   # Open connection",
        "    try:",
        "        yield db          # Provide session to endpoint",
        "    finally:",
        "        db.close()        # Always close, even on errors",
        "",
        "@app.get('/transactions/{transaction_id}')",
        "def get_transaction(",
        "    transaction_id: str,",
        "    db: Session = Depends(get_db)   # DB session injected automatically",
        "):",
        "    txn = db.query(Transaction).filter(Transaction.id == transaction_id).first()",
        "    if not txn:",
        "        raise HTTPException(status_code=404, detail='Transaction not found')",
        "    return txn",
    ])
    story += PBR()

    # ═══════════════════════════════════════════════
    # CHAPTER 11 — Authentication
    # ═══════════════════════════════════════════════
    story += chapter_header("11", "Authentication",
        "JWT, OAuth2, password hashing, and protecting your fraud detection API")

    story += H2("11.1 Why Authentication Matters in Fraud Detection")
    story += P("A fraud detection API contains some of the most sensitive data imaginable — transaction histories, fraud scores, customer risk profiles, and ML model details. Without authentication, anyone with the URL could:")
    story += B("Access all customer transaction data (regulatory violation)")
    story += B("Query fraud scores to understand how to evade detection")
    story += B("Inject fake transactions to game the system")
    story += B("Modify fraud flags to unblock their own fraudulent transactions")
    story += SP()
    story += P("We will implement <b>OAuth2 with JWT (JSON Web Tokens)</b> — the industry standard for REST API authentication.")

    story += H2("11.2 Password Hashing")
    story += P("Passwords must <b>never</b> be stored in plain text. If your database is compromised, plain text passwords immediately give attackers access to all accounts. We use <b>bcrypt</b> hashing.")
    story += code_block([
        "# Install: pip install passlib[bcrypt]",
        "from passlib.context import CryptContext",
        "",
        "# Create a password context with bcrypt algorithm",
        "pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')",
        "",
        "def hash_password(plain_password: str) -> str:",
        "    '''",
        "    Hash a plain text password for storage.",
        "    bcrypt automatically adds a salt — same password hashes differently each time!",
        "    '''",
        "    return pwd_context.hash(plain_password)",
        "",
        "def verify_password(plain_password: str, hashed_password: str) -> bool:",
        "    '''Verify a plain password against a stored hash.'''",
        "    return pwd_context.verify(plain_password, hashed_password)",
        "",
        "# Example",
        "hashed = hash_password('my_secure_password_123')",
        "print(hashed)  # $2b$12$randomsalthereHASHEDVALUE",
        "",
        "# Verify — True",
        "print(verify_password('my_secure_password_123', hashed))  # True",
        "print(verify_password('wrong_password', hashed))          # False",
    ])

    story += H2("11.3 JWT — JSON Web Tokens")
    story += P("A JWT is a compact, URL-safe token that securely transmits information between parties. It consists of three parts separated by dots:")
    story += ascii_diagram([
        "  eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyXzEyMyIsInJvbGUiOiJhbmFseXN0In0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c",
        "  |___________________________________|.|___________________________________|.|_____________|",
        "           HEADER (Base64)                    PAYLOAD (Base64)               SIGNATURE",
        "",
        "  Header:    {'alg': 'HS256', 'typ': 'JWT'}",
        "  Payload:   {'sub': 'user_123', 'role': 'analyst', 'exp': 1718000000}",
        "  Signature: HMACSHA256(header + '.' + payload, SECRET_KEY)",
    ])
    story += code_block([
        "# Install: pip install python-jose[cryptography]",
        "from jose import JWTError, jwt",
        "from datetime import datetime, timedelta",
        "",
        "SECRET_KEY = 'your-super-secret-key-store-in-env-not-code'",
        "ALGORITHM = 'HS256'",
        "ACCESS_TOKEN_EXPIRE_MINUTES = 30",
        "",
        "def create_access_token(data: dict, expires_delta: timedelta = None) -> str:",
        "    '''",
        "    Create a signed JWT token.",
        "    'data' contains claims — information about the user.",
        "    '''",
        "    to_encode = data.copy()",
        "",
        "    # Set expiration time",
        "    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))",
        "    to_encode.update({'exp': expire})",
        "",
        "    # Sign and encode the token",
        "    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)",
        "",
        "def decode_token(token: str) -> dict:",
        "    '''Decode and verify a JWT token. Raises JWTError if invalid/expired.'''",
        "    try:",
        "        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])",
        "        return payload",
        "    except JWTError:",
        "        raise HTTPException(status_code=401, detail='Invalid or expired token')",
        "",
        "# Example usage",
        "token = create_access_token({'sub': 'analyst_jane', 'role': 'senior_analyst'})",
        "print(token)   # eyJhbGciOiJIUzI1NiJ9...",
        "",
        "payload = decode_token(token)",
        "print(payload['sub'])    # analyst_jane",
        "print(payload['role'])   # senior_analyst",
    ])

    story += H2("11.4 Full Authentication Flow")
    story += code_block([
        "from fastapi import FastAPI, Depends, HTTPException, status",
        "from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm",
        "from pydantic import BaseModel",
        "",
        "app = FastAPI()",
        "",
        "# This tells FastAPI where clients can get tokens",
        "oauth2_scheme = OAuth2PasswordBearer(tokenUrl='auth/token')",
        "",
        "# Simulated user database",
        "fake_users_db = {",
        "    'analyst_jane': {",
        "        'username': 'analyst_jane',",
        "        'hashed_password': hash_password('securepass123'),",
        "        'role': 'senior_analyst',",
        "        'disabled': False",
        "    }",
        "}",
        "",
        "class TokenResponse(BaseModel):",
        "    access_token: str",
        "    token_type: str",
        "",
        "@app.post('/auth/token', response_model=TokenResponse)",
        "def login(form_data: OAuth2PasswordRequestForm = Depends()):",
        "    '''",
        "    Login endpoint — exchanges username/password for a JWT token.",
        "    OAuth2PasswordRequestForm automatically parses form data.",
        "    '''",
        "    user = fake_users_db.get(form_data.username)",
        "    if not user or not verify_password(form_data.password, user['hashed_password']):",
        "        raise HTTPException(",
        "            status_code=status.HTTP_401_UNAUTHORIZED,",
        "            detail='Invalid credentials',",
        "            headers={'WWW-Authenticate': 'Bearer'}",
        "        )",
        "",
        "    token = create_access_token({'sub': user['username'], 'role': user['role']})",
        "    return {'access_token': token, 'token_type': 'bearer'}",
        "",
        "# Dependency: extract and verify current user from token",
        "async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:",
        "    payload = decode_token(token)",
        "    username = payload.get('sub')",
        "    user = fake_users_db.get(username)",
        "    if not user:",
        "        raise HTTPException(status_code=401, detail='User not found')",
        "    return user",
        "",
        "# Protected endpoint — requires valid JWT",
        "@app.get('/transactions')",
        "def list_transactions(current_user: dict = Depends(get_current_user)):",
        "    return {'user': current_user['username'], 'transactions': []}",
    ])
    story += warn("Never hard-code your SECRET_KEY in your code. Store it in environment variables. If someone gets your SECRET_KEY, they can forge valid JWT tokens and bypass all authentication.")
    story += PBR()

    # ═══════════════════════════════════════════════
    # CHAPTER 12 — Databases
    # ═══════════════════════════════════════════════
    story += chapter_header("12", "Databases with SQLAlchemy and Alembic",
        "Persisting transactions, fraud scores, and customer data professionally")

    story += H2("12.1 Setting Up SQLAlchemy")
    story += P("SQLAlchemy is the most popular Python ORM (Object Relational Mapper). It allows you to interact with databases using Python objects instead of raw SQL queries.")
    story += code_block([
        "# Install: pip install sqlalchemy databases[sqlite] alembic",
        "# database.py",
        "",
        "from sqlalchemy import create_engine",
        "from sqlalchemy.ext.declarative import declarative_base",
        "from sqlalchemy.orm import sessionmaker",
        "",
        "# Database URL format:",
        "# sqlite:///./fraud_system.db  (SQLite — development)",
        "# postgresql://user:password@host:port/dbname  (PostgreSQL — production)",
        "DATABASE_URL = 'sqlite:///./fraud_system.db'",
        "",
        "# Create the engine — the connection to the database",
        "engine = create_engine(",
        "    DATABASE_URL,",
        "    connect_args={'check_same_thread': False}  # Required for SQLite only",
        ")",
        "",
        "# SessionLocal is a factory that creates database sessions",
        "SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)",
        "",
        "# Base class for our SQLAlchemy models",
        "Base = declarative_base()",
    ])

    story += H2("12.2 Defining Database Models")
    story += code_block([
        "# models/transaction.py",
        "from sqlalchemy import Column, String, Float, Boolean, DateTime, Integer, ForeignKey",
        "from sqlalchemy.orm import relationship",
        "from datetime import datetime",
        "from database import Base",
        "",
        "class Transaction(Base):",
        "    __tablename__ = 'transactions'   # Name of the database table",
        "",
        "    # Primary key — auto-incrementing integer",
        "    id = Column(Integer, primary_key=True, index=True)",
        "",
        "    # Transaction fields",
        "    transaction_id = Column(String, unique=True, index=True)",
        "    amount = Column(Float, nullable=False)",
        "    currency = Column(String(3), default='KES')",
        "    customer_id = Column(String, index=True)",
        "    merchant = Column(String)",
        "    location = Column(String, nullable=True)",
        "    payment_method = Column(String, default='CARD')",
        "",
        "    # Fraud detection fields",
        "    fraud_score = Column(Float, default=0.0)",
        "    risk_level = Column(String, default='LOW')",
        "    flagged = Column(Boolean, default=False)",
        "    reviewed = Column(Boolean, default=False)",
        "    reviewed_by = Column(String, nullable=True)",
        "",
        "    # Timestamps",
        "    created_at = Column(DateTime, default=datetime.utcnow)",
        "    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)",
    ])

    story += H2("12.3 CRUD Operations with SQLAlchemy")
    story += code_block([
        "# services/transaction_service.py",
        "from sqlalchemy.orm import Session",
        "from models.transaction import Transaction",
        "from schemas.transaction import TransactionCreate",
        "import uuid",
        "",
        "def create_transaction(db: Session, data: TransactionCreate) -> Transaction:",
        "    '''Create and persist a new transaction.'''",
        "    txn = Transaction(",
        "        transaction_id=f'TXN-{uuid.uuid4().hex[:8].upper()}',",
        "        amount=data.amount,",
        "        currency=data.currency,",
        "        customer_id=data.customer_id,",
        "        merchant=data.merchant,",
        "        location=data.location,",
        "        payment_method=data.payment_method",
        "    )",
        "    db.add(txn)       # Stage the transaction",
        "    db.commit()       # Write to database",
        "    db.refresh(txn)   # Reload from database (to get auto-generated fields)",
        "    return txn",
        "",
        "def get_transaction(db: Session, transaction_id: str) -> Transaction:",
        "    return db.query(Transaction).filter(",
        "        Transaction.transaction_id == transaction_id",
        "    ).first()",
        "",
        "def get_customer_transactions(",
        "    db: Session, customer_id: str, skip: int = 0, limit: int = 20",
        ") -> list:",
        "    return db.query(Transaction).filter(",
        "        Transaction.customer_id == customer_id",
        "    ).offset(skip).limit(limit).all()",
        "",
        "def get_flagged_transactions(db: Session, limit: int = 50) -> list:",
        "    return db.query(Transaction).filter(",
        "        Transaction.flagged == True",
        "    ).order_by(",
        "        Transaction.created_at.desc()",
        "    ).limit(limit).all()",
    ])
    story += PBR()

    # ═══════════════════════════════════════════════
    # CHAPTER 13 — Error Handling
    # ═══════════════════════════════════════════════
    story += chapter_header("13", "Error Handling",
        "Returning meaningful errors that help clients recover gracefully")

    story += H2("13.1 HTTPException — The Standard Way")
    story += code_block([
        "from fastapi import FastAPI, HTTPException, status",
        "",
        "app = FastAPI()",
        "",
        "@app.get('/transactions/{transaction_id}')",
        "def get_transaction(transaction_id: str, db: Session = Depends(get_db)):",
        "    txn = db.query(Transaction).filter(",
        "        Transaction.transaction_id == transaction_id",
        "    ).first()",
        "",
        "    if not txn:",
        "        raise HTTPException(",
        "            status_code=status.HTTP_404_NOT_FOUND,  # Use constants for clarity",
        "            detail=f'Transaction {transaction_id} was not found in the system.',",
        "        )",
        "    return txn",
    ])

    story += H2("13.2 Custom Exception Handlers")
    story += code_block([
        "from fastapi import FastAPI, Request",
        "from fastapi.responses import JSONResponse",
        "",
        "app = FastAPI()",
        "",
        "# Custom exception class",
        "class FraudDetectionException(Exception):",
        "    def __init__(self, message: str, error_code: str, status_code: int = 400):",
        "        self.message = message",
        "        self.error_code = error_code",
        "        self.status_code = status_code",
        "",
        "# Register a handler for this exception type",
        "@app.exception_handler(FraudDetectionException)",
        "async def fraud_exception_handler(request: Request, exc: FraudDetectionException):",
        "    return JSONResponse(",
        "        status_code=exc.status_code,",
        "        content={",
        "            'error': True,",
        "            'error_code': exc.error_code,",
        "            'message': exc.message,",
        "            'path': str(request.url),",
        "        }",
        "    )",
        "",
        "# Use the custom exception",
        "@app.post('/transactions')",
        "def create_transaction(data: TransactionCreate, db: Session = Depends(get_db)):",
        "    # Check for duplicate transaction",
        "    existing = db.query(Transaction).filter(",
        "        Transaction.transaction_id == data.transaction_id",
        "    ).first()",
        "    if existing:",
        "        raise FraudDetectionException(",
        "            message=f'Transaction {data.transaction_id} already exists.',",
        "            error_code='DUPLICATE_TRANSACTION',",
        "            status_code=409",
        "        )",
    ])
    story += PBR()

    # ═══════════════════════════════════════════════
    # CHAPTERS 14-16 — Middleware, Background Tasks, Uploads
    # ═══════════════════════════════════════════════
    story += chapter_header("14", "Middleware, Background Tasks and File Uploads",
        "Advanced FastAPI features for production-ready APIs")

    story += H2("14.1 Middleware")
    story += P("Middleware is code that runs <b>before and after every request</b>. It's perfect for logging, timing, CORS, and adding headers.")
    story += code_block([
        "from fastapi import FastAPI, Request",
        "from fastapi.middleware.cors import CORSMiddleware",
        "import time, uuid",
        "",
        "app = FastAPI()",
        "",
        "# CORS Middleware — allows browsers from other domains to call your API",
        "app.add_middleware(",
        "    CORSMiddleware,",
        "    allow_origins=['https://fraud-dashboard.mybank.co.ke', 'http://localhost:3000'],",
        "    allow_credentials=True,",
        "    allow_methods=['*'],",
        "    allow_headers=['*'],",
        ")",
        "",
        "# Custom middleware for logging and timing",
        "@app.middleware('http')",
        "async def log_requests(request: Request, call_next):",
        "    request_id = str(uuid.uuid4())[:8]",
        "    start_time = time.time()",
        "",
        "    # Process the request",
        "    response = await call_next(request)",
        "",
        "    # Log after response",
        "    duration_ms = (time.time() - start_time) * 1000",
        "    print(f'[{request_id}] {request.method} {request.url.path} -> {response.status_code} ({duration_ms:.1f}ms)')",
        "",
        "    # Add custom headers to every response",
        "    response.headers['X-Request-ID'] = request_id",
        "    response.headers['X-Response-Time'] = f'{duration_ms:.1f}ms'",
        "    return response",
    ])

    story += H2("15.1 Background Tasks")
    story += P("Background tasks run <b>after the response is sent</b>. Perfect for sending notifications or updating fraud reports without making the client wait.")
    story += code_block([
        "from fastapi import BackgroundTasks",
        "",
        "def send_fraud_alert(customer_id: str, transaction_id: str, fraud_score: float):",
        "    '''This runs after the HTTP response is already sent to the client.'''",
        "    print(f'[ALERT] Customer {customer_id} — Transaction {transaction_id} fraud score: {fraud_score}')",
        "    # In production: send SMS via Africastalking, email via SendGrid, etc.",
        "",
        "@app.post('/transactions', status_code=201)",
        "def create_transaction(",
        "    data: TransactionCreate,",
        "    background_tasks: BackgroundTasks,",
        "    db: Session = Depends(get_db)",
        "):",
        "    # Create transaction and get fraud score ...",
        "    txn = create_transaction_in_db(db, data)",
        "",
        "    # Schedule the alert — runs AFTER we return the response",
        "    if txn.fraud_score > 0.7:",
        "        background_tasks.add_task(",
        "            send_fraud_alert,",
        "            txn.customer_id,",
        "            txn.transaction_id,",
        "            txn.fraud_score",
        "        )",
        "",
        "    return txn  # Client gets response immediately",
    ])

    story += H2("16.1 File Uploads")
    story += P("FastAPI supports file uploads for bulk transaction imports, supporting document uploads, and more.")
    story += code_block([
        "from fastapi import UploadFile, File",
        "import csv, io",
        "",
        "@app.post('/transactions/bulk-import')",
        "async def bulk_import_transactions(",
        "    file: UploadFile = File(..., description='CSV file with transaction records'),",
        "    current_user: dict = Depends(get_current_user)",
        "):",
        "    '''Upload a CSV file containing multiple transactions for batch fraud analysis.'''",
        "    if not file.filename.endswith('.csv'):",
        "        raise HTTPException(400, 'Only CSV files are accepted')",
        "",
        "    contents = await file.read()",
        "    decoded = contents.decode('utf-8')",
        "    reader = csv.DictReader(io.StringIO(decoded))",
        "",
        "    transactions = []",
        "    for row in reader:",
        "        transactions.append({",
        "            'amount': float(row['amount']),",
        "            'customer_id': row['customer_id'],",
        "            'merchant': row['merchant']",
        "        })",
        "",
        "    return {",
        "        'imported': len(transactions),",
        "        'filename': file.filename,",
        "        'status': 'queued_for_analysis'",
        "    }",
    ])
    story += PBR()

    # ═══════════════════════════════════════════════
    # CHAPTER 17 — Testing
    # ═══════════════════════════════════════════════
    story += chapter_header("17", "Testing APIs with pytest and TestClient",
        "Writing tests that prove your fraud detection API works correctly")

    story += H2("17.1 Why Testing Is Non-Negotiable")
    story += P("In a fraud detection system, bugs have real financial consequences. A false negative (missing real fraud) means real money is stolen. A false positive (blocking legitimate transactions) means customer frustration and lost revenue. Tests are your safety net.")

    story += H2("17.2 Setting Up Testing")
    story += code_block([
        "# Install: pip install pytest httpx",
        "# tests/test_transactions.py",
        "",
        "import pytest",
        "from fastapi.testclient import TestClient",
        "from sqlalchemy import create_engine",
        "from sqlalchemy.orm import sessionmaker",
        "from main import app",
        "from database import Base, get_db",
        "",
        "# Use a separate in-memory SQLite database for testing",
        "TEST_DATABASE_URL = 'sqlite:///./test_fraud.db'",
        "engine = create_engine(TEST_DATABASE_URL, connect_args={'check_same_thread': False})",
        "TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)",
        "",
        "def override_get_db():",
        "    db = TestingSessionLocal()",
        "    try:",
        "        yield db",
        "    finally:",
        "        db.close()",
        "",
        "# Override the real DB with test DB",
        "app.dependency_overrides[get_db] = override_get_db",
        "",
        "# Create test tables",
        "Base.metadata.create_all(bind=engine)",
        "",
        "# Create test client",
        "client = TestClient(app)",
    ])

    story += H2("17.3 Writing Tests")
    story += code_block([
        "# tests/test_transactions.py (continued)",
        "",
        "def test_root_endpoint():",
        "    '''Test that the root endpoint returns 200 and correct message.'''",
        "    response = client.get('/')",
        "    assert response.status_code == 200",
        "    data = response.json()",
        "    assert 'message' in data",
        "",
        "def test_create_transaction_success():",
        "    '''Test that a valid transaction is created and scored.'''",
        "    payload = {",
        "        'amount': 5000.00,",
        "        'currency': 'KES',",
        "        'customer_id': 'KE-TEST-001',",
        "        'merchant': 'Test Merchant',",
        "        'payment_method': 'CARD'",
        "    }",
        "    response = client.post('/transactions', json=payload)",
        "    assert response.status_code == 201",
        "    data = response.json()",
        "    assert 'transaction_id' in data",
        "    assert 'fraud_score' in data",
        "    assert 0 <= data['fraud_score'] <= 1",
        "",
        "def test_create_transaction_invalid_amount():",
        "    '''Test that negative amounts are rejected with 422.'''",
        "    payload = {",
        "        'amount': -500.00,   # Invalid!",
        "        'currency': 'KES',",
        "        'customer_id': 'KE-TEST-001',",
        "        'merchant': 'Test Merchant'",
        "    }",
        "    response = client.post('/transactions', json=payload)",
        "    assert response.status_code == 422",
        "",
        "def test_get_nonexistent_transaction():",
        "    response = client.get('/transactions/FAKE-ID-DOES-NOT-EXIST')",
        "    assert response.status_code == 404",
        "",
        "def test_high_value_transaction_flagged():",
        "    '''Fraud detection: transactions over 100,000 KES should be flagged.'''",
        "    payload = {",
        "        'amount': 250000.00,   # Very high amount",
        "        'currency': 'KES',",
        "        'customer_id': 'KE-TEST-002',",
        "        'merchant': 'Unknown Overseas Merchant'",
        "    }",
        "    response = client.post('/transactions', json=payload)",
        "    assert response.status_code == 201",
        "    data = response.json()",
        "    assert data['fraud_score'] > 0.5, 'High-value transaction should have elevated fraud score'",
        "",
        "# Run tests:",
        "# pytest tests/ -v",
        "# pytest tests/ -v --cov=app --cov-report=html",
    ])
    story += PBR()

    # ═══════════════════════════════════════════════
    # CHAPTER 18 — Docker
    # ═══════════════════════════════════════════════
    story += chapter_header("18", "Dockerising FastAPI",
        "Packaging your API into a portable, reproducible container")

    story += H2("18.1 What Is Docker?")
    story += P("Docker is a platform that packages your application and all its dependencies into a portable unit called a <b>container</b>. A container runs the same way on any machine — your laptop, a server in Nairobi, or a cloud server in London.")
    story += P("For fraud detection APIs, Docker solves the 'works on my machine' problem and enables consistent deployment across development, testing, and production environments.")

    story += H2("18.2 The Dockerfile")
    story += code_block([
        "# Dockerfile",
        "",
        "# Start from an official Python image",
        "FROM python:3.11-slim",
        "",
        "# Set working directory inside the container",
        "WORKDIR /app",
        "",
        "# Copy requirements first (better Docker layer caching)",
        "COPY requirements.txt .",
        "",
        "# Install Python dependencies",
        "RUN pip install --no-cache-dir -r requirements.txt",
        "",
        "# Copy the rest of the application code",
        "COPY . .",
        "",
        "# Expose port 8000 (the port FastAPI runs on)",
        "EXPOSE 8000",
        "",
        "# Command to run the application",
        "CMD ['uvicorn', 'main:app', '--host', '0.0.0.0', '--port', '8000']",
    ])
    story += code_block([
        "# .dockerignore — files to exclude from the Docker build",
        "__pycache__/",
        "*.pyc",
        "*.pyo",
        ".env",
        "*.db",
        "fraud_api_env/",
        "tests/",
        ".git/",
    ])
    story += code_block([
        "# docker-compose.yml — orchestrate multiple services",
        "version: '3.9'",
        "",
        "services:",
        "  # The FastAPI application",
        "  api:",
        "    build: .",
        "    ports:",
        "      - '8000:8000'",
        "    environment:",
        "      - DATABASE_URL=postgresql://fraud_user:password@db:5432/fraud_db",
        "      - SECRET_KEY=your-production-secret-key",
        "    depends_on:",
        "      - db",
        "    volumes:",
        "      - .:/app   # Mount code for development hot-reload",
        "",
        "  # PostgreSQL database",
        "  db:",
        "    image: postgres:15",
        "    environment:",
        "      - POSTGRES_DB=fraud_db",
        "      - POSTGRES_USER=fraud_user",
        "      - POSTGRES_PASSWORD=password",
        "    volumes:",
        "      - postgres_data:/var/lib/postgresql/data",
        "",
        "volumes:",
        "  postgres_data:",
        "",
        "# Commands:",
        "# docker-compose up --build    (first time or after code changes)",
        "# docker-compose up -d         (run in background)",
        "# docker-compose down          (stop and remove containers)",
        "# docker-compose logs api      (view API logs)",
    ])
    story += PBR()

    # ═══════════════════════════════════════════════
    # CHAPTER 19 — Deployment
    # ═══════════════════════════════════════════════
    story += chapter_header("19", "Deploying FastAPI",
        "Getting your fraud detection API live on the internet")

    story += H2("19.1 Deployment Options")
    story += two_col_table(
        ["Platform", "Best For", "Cost", "Notes"],
        [
            ["Render", "Side projects, small APIs", "Free tier available", "Easy, automatic deploys from GitHub"],
            ["Railway", "Small to medium APIs", "Pay as you use", "Great developer experience, fast setup"],
            ["Heroku", "Simple deployments", "Free tier removed", "Well-documented, easy to use"],
            ["AWS (ECS/EKS)", "Enterprise, high traffic", "Varies by usage", "Most powerful, steepest learning curve"],
            ["Google Cloud Run", "Serverless containers", "Pay per request", "Excellent for variable traffic"],
            ["Azure Container Apps", "Enterprise Microsoft stack", "Varies", "Good Azure/AD integration"],
            ["DigitalOcean App Platform", "Small to medium", "From $5/month", "Simple interface, good value"],
        ],
        [3*cm, 3.5*cm, 2.5*cm, 6.5*cm]
    )

    story += H2("19.2 Deploying to Render (Step by Step)")
    story += code_block([
        "# Step 1: Create requirements.txt",
        "pip freeze > requirements.txt",
        "",
        "# Step 2: Create a Procfile (tells Render how to start your app)",
        "# Procfile (no extension)",
        "web: uvicorn main:app --host 0.0.0.0 --port $PORT",
        "",
        "# Step 3: Push to GitHub",
        "git init",
        "git add .",
        "git commit -m 'Initial fraud detection API'",
        "git remote add origin https://github.com/yourusername/fraud-api.git",
        "git push -u origin main",
        "",
        "# Step 4: Go to render.com",
        "# - Click 'New' -> 'Web Service'",
        "# - Connect your GitHub repository",
        "# - Set environment variables (SECRET_KEY, DATABASE_URL)",
        "# - Click 'Deploy'",
        "",
        "# Your API will be live at: https://fraud-api.onrender.com",
    ])

    story += H2("19.3 Environment Variables")
    story += code_block([
        "# .env file (never commit to Git!)",
        "SECRET_KEY=super-secret-production-key-minimum-32-characters",
        "DATABASE_URL=postgresql://user:pass@localhost/fraud_db",
        "ML_MODEL_PATH=/app/models/fraud_detector_v2.pkl",
        "API_KEY_SALT=another-secret-salt",
        "ALLOWED_ORIGINS=https://dashboard.mybank.co.ke",
        "",
        "# config.py — loading environment variables",
        "from pydantic import BaseSettings",
        "",
        "class Settings(BaseSettings):",
        "    secret_key: str",
        "    database_url: str",
        "    ml_model_path: str = '/app/models/default.pkl'",
        "    allowed_origins: str = 'http://localhost:3000'",
        "",
        "    class Config:",
        "        env_file = '.env'",
        "",
        "settings = Settings()",
    ])
    story += PBR()

    # ═══════════════════════════════════════════════
    # CHAPTER 20 — Fraud Detection API (Capstone)
    # ═══════════════════════════════════════════════
    story += chapter_header("20", "Capstone: Building a Fraud Detection API",
        "A complete, production-ready fraud detection system integrating ML with FastAPI")

    story += H2("20.1 System Architecture")
    story += P("In this capstone, we build a fully functional fraud detection API that could realistically be deployed by a bank or mobile money operator in Kenya. The system includes authentication, transaction processing, ML fraud scoring, and a complete audit trail.")
    story += ascii_diagram([
        "  ┌──────────────────────────────────────────────────────────────┐",
        "  │                  FRAUD DETECTION SYSTEM                      │",
        "  │                                                              │",
        "  │  ┌──────────┐   JWT Auth    ┌─────────────────────────────┐ │",
        "  │  │  Mobile  │ ─────────────>│     FastAPI Application     │ │",
        "  │  │   App    │               │                             │ │",
        "  │  └──────────┘               │  ┌─────────┐  ┌─────────┐  │ │",
        "  │                             │  │  Auth   │  │  Trans  │  │ │",
        "  │  ┌──────────┐               │  │ Router  │  │ Router  │  │ │",
        "  │  │  POS     │ ─────────────>│  └────┬────┘  └────┬────┘  │ │",
        "  │  │ Terminal │               │       │             │       │ │",
        "  │  └──────────┘               │  ┌────▼─────────────▼────┐  │ │",
        "  │                             │  │    Dependency Layer    │  │ │",
        "  │  ┌──────────┐               │  │  (Auth + DB Session)   │  │ │",
        "  │  │ Analyst  │ ─────────────>│  └────────────┬──────────┘  │ │",
        "  │  │Dashboard │               │               │             │ │",
        "  │  └──────────┘               │  ┌────────────▼──────────┐  │ │",
        "  │                             │  │   Services Layer       │  │ │",
        "  │                             │  │  FraudDetectorService  │  │ │",
        "  │                             │  │  ML Model (sklearn)    │  │ │",
        "  │                             │  └────────────┬──────────┘  │ │",
        "  │                             │               │             │ │",
        "  │                             │  ┌────────────▼──────────┐  │ │",
        "  │                             │  │  PostgreSQL Database   │  │ │",
        "  │                             │  │  transactions table    │  │ │",
        "  │                             │  │  customers table       │  │ │",
        "  │                             │  │  fraud_logs table      │  │ │",
        "  │                             │  └───────────────────────┘  │ │",
        "  │                             └─────────────────────────────┘ │",
        "  └──────────────────────────────────────────────────────────────┘",
    ])

    story += H2("20.2 Project Structure")
    story += code_block([
        "fraud_detection_api/",
        "├── main.py",
        "├── requirements.txt",
        "├── .env",
        "├── Dockerfile",
        "├── docker-compose.yml",
        "│",
        "├── app/",
        "│   ├── __init__.py",
        "│   ├── config.py           # Environment variable settings",
        "│   ├── database.py         # SQLAlchemy engine and session",
        "│   │",
        "│   ├── models/",
        "│   │   ├── user.py         # User accounts for analysts",
        "│   │   ├── transaction.py  # Transaction records",
        "│   │   └── fraud_log.py    # Fraud scoring audit trail",
        "│   │",
        "│   ├── schemas/",
        "│   │   ├── user.py",
        "│   │   ├── transaction.py",
        "│   │   └── fraud.py",
        "│   │",
        "│   ├── routers/",
        "│   │   ├── auth.py         # Login, register, refresh token",
        "│   │   ├── transactions.py # Full CRUD + fraud scoring",
        "│   │   └── analytics.py    # Fraud statistics and reports",
        "│   │",
        "│   ├── services/",
        "│   │   ├── fraud_detector.py  # ML model integration",
        "│   │   └── auth_service.py    # JWT and password logic",
        "│   │",
        "│   ├── ml/",
        "│   │   ├── model.pkl       # Trained fraud detection model",
        "│   │   └── train.py        # Script to train the model",
        "│   │",
        "│   └── dependencies.py     # get_db, get_current_user",
        "│",
        "└── tests/",
        "    ├── test_auth.py",
        "    ├── test_transactions.py",
        "    └── test_fraud_detection.py",
    ])

    story += H2("20.3 The ML Fraud Detection Model")
    story += P("We use scikit-learn to train a simple but effective fraud detection model. In a real bank, this would be replaced by a more sophisticated model trained on millions of real transactions.")
    story += code_block([
        "# app/ml/train.py — Train the fraud detection model",
        "import numpy as np",
        "import pandas as pd",
        "from sklearn.ensemble import RandomForestClassifier",
        "from sklearn.preprocessing import LabelEncoder",
        "from sklearn.model_selection import train_test_split",
        "from sklearn.metrics import classification_report",
        "import pickle",
        "",
        "# Generate synthetic training data (in production, use real transaction data)",
        "np.random.seed(42)",
        "n_samples = 10000",
        "",
        "# Generate features",
        "amounts = np.random.exponential(scale=5000, size=n_samples)",
        "hours = np.random.randint(0, 24, size=n_samples)",
        "is_new_merchant = np.random.randint(0, 2, size=n_samples)",
        "rapid_succession = np.random.randint(0, 2, size=n_samples)",
        "international = np.random.randint(0, 2, size=n_samples)",
        "",
        "# Create fraud labels based on rules (simulating real fraud patterns)",
        "fraud = (",
        "    (amounts > 50000).astype(int) * 0.4 +",
        "    is_new_merchant * 0.3 +",
        "    rapid_succession * 0.5 +",
        "    international * 0.4 +",
        "    ((hours < 4) | (hours > 22)).astype(int) * 0.3",
        ") > 0.7",
        "",
        "# Build DataFrame",
        "df = pd.DataFrame({",
        "    'amount': amounts,",
        "    'hour_of_day': hours,",
        "    'is_new_merchant': is_new_merchant,",
        "    'rapid_succession': rapid_succession,",
        "    'is_international': international,",
        "    'is_fraud': fraud.astype(int)",
        "})",
        "",
        "X = df.drop('is_fraud', axis=1)",
        "y = df['is_fraud']",
        "",
        "X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)",
        "",
        "# Train Random Forest model",
        "model = RandomForestClassifier(n_estimators=100, random_state=42)",
        "model.fit(X_train, y_train)",
        "",
        "# Evaluate",
        "y_pred = model.predict(X_test)",
        "print(classification_report(y_test, y_pred))",
        "",
        "# Save the model",
        "with open('app/ml/model.pkl', 'wb') as f:",
        "    pickle.dump(model, f)",
        "",
        "print('Model saved to app/ml/model.pkl')",
    ])

    story += H2("20.4 The Fraud Detector Service")
    story += code_block([
        "# app/services/fraud_detector.py",
        "import pickle",
        "import numpy as np",
        "from datetime import datetime",
        "from typing import Dict, Tuple",
        "",
        "class FraudDetectorService:",
        "    '''",
        "    Service class that wraps the ML model and provides",
        "    fraud scoring functionality.",
        "    '''",
        "    _instance = None   # Singleton pattern — load model only once",
        "",
        "    def __new__(cls):",
        "        if cls._instance is None:",
        "            cls._instance = super().__new__(cls)",
        "            cls._instance._load_model()",
        "        return cls._instance",
        "",
        "    def _load_model(self):",
        "        '''Load the ML model from disk on first use.'''",
        "        with open('app/ml/model.pkl', 'rb') as f:",
        "            self.model = pickle.load(f)",
        "        self.model_version = 'fraud-detector-v1.0'",
        "        print(f'[FraudDetector] Model {self.model_version} loaded.')",
        "",
        "    def extract_features(self, transaction: dict) -> np.ndarray:",
        "        '''",
        "        Extract numerical features from a transaction for the ML model.",
        "        This is called 'feature engineering'.",
        "        '''",
        "        timestamp = transaction.get('timestamp', datetime.utcnow())",
        "        if isinstance(timestamp, str):",
        "            timestamp = datetime.fromisoformat(timestamp)",
        "",
        "        features = [",
        "            transaction['amount'],",
        "            timestamp.hour,",
        "            int(transaction.get('is_new_merchant', False)),",
        "            int(transaction.get('rapid_succession', False)),",
        "            int(transaction.get('is_international', False))",
        "        ]",
        "        return np.array(features).reshape(1, -1)",
        "",
        "    def predict(self, transaction: dict) -> Tuple[float, str]:",
        "        '''",
        "        Generate a fraud score and risk level for a transaction.",
        "        Returns: (fraud_score: float, risk_level: str)",
        "        '''",
        "        features = self.extract_features(transaction)",
        "",
        "        # Get probability of fraud (class 1)",
        "        fraud_probability = self.model.predict_proba(features)[0][1]",
        "        fraud_score = round(float(fraud_probability), 4)",
        "",
        "        # Map score to risk level",
        "        if fraud_score >= 0.9:",
        "            risk_level = 'CRITICAL'",
        "        elif fraud_score >= 0.7:",
        "            risk_level = 'HIGH'",
        "        elif fraud_score >= 0.4:",
        "            risk_level = 'MEDIUM'",
        "        else:",
        "            risk_level = 'LOW'",
        "",
        "        return fraud_score, risk_level",
    ])

    story += H2("20.5 The Complete Transaction Router")
    story += code_block([
        "# app/routers/transactions.py",
        "from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status",
        "from sqlalchemy.orm import Session",
        "from typing import List, Optional",
        "from datetime import datetime",
        "",
        "from app.database import get_db",
        "from app.dependencies import get_current_user",
        "from app.models.transaction import Transaction",
        "from app.schemas.transaction import TransactionCreate, TransactionResponse",
        "from app.services.fraud_detector import FraudDetectorService",
        "import uuid, logging",
        "",
        "router = APIRouter(prefix='/transactions', tags=['Transactions'])",
        "logger = logging.getLogger(__name__)",
        "fraud_detector = FraudDetectorService()   # Singleton — model loaded once",
        "",
        "@router.post('/', response_model=TransactionResponse, status_code=201)",
        "async def submit_transaction(",
        "    data: TransactionCreate,",
        "    background_tasks: BackgroundTasks,",
        "    db: Session = Depends(get_db),",
        "    current_user: dict = Depends(get_current_user)",
        "):",
        "    '''",
        "    Submit a transaction for real-time fraud analysis.",
        "    Returns a fraud score, risk level, and recommended action.",
        "    '''",
        "    logger.info(f'Transaction submitted by {current_user[\"username\"]}')",
        "",
        "    # Check for duplicate transaction ID",
        "    existing = db.query(Transaction).filter(",
        "        Transaction.transaction_id == data.transaction_id",
        "    ).first()",
        "    if existing:",
        "        raise HTTPException(status_code=409, detail='Duplicate transaction ID')",
        "",
        "    # Run fraud detection",
        "    fraud_score, risk_level = fraud_detector.predict(data.dict())",
        "",
        "    # Determine action based on risk",
        "    action = 'ALLOW'",
        "    if fraud_score >= 0.9:",
        "        action = 'BLOCK'",
        "    elif fraud_score >= 0.7:",
        "        action = 'REVIEW'",
        "",
        "    # Create transaction record",
        "    txn = Transaction(",
        "        transaction_id=data.transaction_id or f'TXN-{uuid.uuid4().hex[:8].upper()}',",
        "        amount=data.amount,",
        "        currency=data.currency,",
        "        customer_id=data.customer_id,",
        "        merchant=data.merchant,",
        "        location=data.location,",
        "        payment_method=data.payment_method,",
        "        fraud_score=fraud_score,",
        "        risk_level=risk_level,",
        "        flagged=(fraud_score >= 0.7),",
        "        action=action,",
        "        submitted_by=current_user['username'],",
        "        created_at=datetime.utcnow()",
        "    )",
        "    db.add(txn)",
        "    db.commit()",
        "    db.refresh(txn)",
        "",
        "    # Send alert in background if high risk",
        "    if fraud_score >= 0.7:",
        "        background_tasks.add_task(",
        "            send_fraud_alert,",
        "            txn.customer_id,",
        "            txn.transaction_id,",
        "            fraud_score,",
        "            risk_level",
        "        )",
        "",
        "    logger.info(f'Transaction {txn.transaction_id}: score={fraud_score}, action={action}')",
        "    return txn",
    ])

    story += H2("20.6 How Banks Use This API")
    story += P("Here is a real-world flow showing how a Kenyan bank's mobile banking app would integrate with this fraud detection API:")
    story += ascii_diagram([
        "  STEP 1: Customer initiates M-Pesa transfer of KES 150,000 at 2:30 AM",
        "",
        "  STEP 2: Mobile Banking Backend sends POST /transactions:",
        "  {",
        '    "amount": 150000,',
        '    "currency": "KES",',
        '    "customer_id": "KE-002341",',
        '    "merchant": "NEW-MERCHANT-Overseas",',
        '    "is_new_merchant": true,',
        '    "is_international": true,',
        '    "timestamp": "2024-06-15T02:30:00Z"',
        "  }",
        "",
        "  STEP 3: FastAPI extracts features and calls ML model",
        "  Amount: 150,000 (large) +0.4",
        "  Hour: 2 AM (off-hours)  +0.3",
        "  New merchant:            +0.3",
        "  International:           +0.4",
        "  Fraud Score: 0.94 -> CRITICAL -> ACTION: BLOCK",
        "",
        "  STEP 4: API returns response:",
        '  {"fraud_score": 0.94, "risk_level": "CRITICAL", "action": "BLOCK"}',
        "",
        "  STEP 5: Mobile Banking Backend blocks the transaction",
        "  Background task: SMS to customer, email to fraud team",
        "",
        "  STEP 6: Fraud analyst reviews via /transactions?flagged=true&min_score=0.9",
    ])

    story += summary_box([
        "The complete fraud detection API combines user authentication, Pydantic validation, SQLAlchemy persistence, ML model integration, background tasks, and Docker deployment.",
        "The ML model uses Random Forest to predict fraud probability based on transaction features.",
        "The FraudDetectorService uses the Singleton pattern so the model is loaded only once at startup.",
        "Background tasks send fraud alerts after the API response is returned — keeping response times fast.",
        "Banks integrate by calling the API synchronously in their transaction processing pipeline.",
    ])
    story += PBR()

    # ═══════════════════════════════════════════════
    # APPENDIX A — Interview Questions
    # ═══════════════════════════════════════════════
    story += chapter_header("A", "100 Interview Questions with Answers",
        "Common questions asked in FastAPI, REST API, and backend engineering interviews")

    story += H2("Section 1: REST API Fundamentals (Q1-25)")
    iq_basic = [
        ("What does REST stand for and what are its six constraints?",
         "REST stands for Representational State Transfer. The six constraints are: Stateless, Client-Server, Cacheable, Uniform Interface, Layered System, and Code on Demand (optional). A system that follows all constraints is called RESTful."),
        ("What is the difference between PUT and PATCH?",
         "PUT replaces an entire resource — all fields must be sent. PATCH partially updates a resource — only the fields to be changed are sent. PUT is idempotent; PATCH is usually but not always idempotent."),
        ("What is idempotency? Which HTTP methods are idempotent?",
         "Idempotency means calling an operation multiple times produces the same result as calling it once. GET, PUT, DELETE, and HEAD are idempotent. POST is not idempotent — each call typically creates a new resource."),
        ("What is the difference between authentication and authorisation?",
         "Authentication verifies WHO you are (e.g., checking your JWT token). Authorisation determines WHAT you are allowed to do (e.g., analysts can view transactions but only admins can delete them)."),
        ("What is a JWT token? What are its three parts?",
         "JWT (JSON Web Token) is a compact, signed token for transmitting user identity. It has three Base64-encoded parts separated by dots: Header (algorithm and type), Payload (claims/user data), and Signature (cryptographic verification)."),
        ("Why should APIs be stateless?",
         "Stateless APIs are easier to scale horizontally — any server can handle any request because no session data is stored on the server. This is essential for high-availability systems like fraud detection where multiple servers share the load."),
        ("What HTTP status code should you return when a resource is not found?",
         "404 Not Found. Reserve 400 for malformed requests (e.g., invalid JSON), 401 for unauthenticated requests, 403 for authorised users without permission, and 422 for requests that pass JSON parsing but fail business validation."),
        ("What is CORS? Why is it needed?",
         "CORS (Cross-Origin Resource Sharing) is a browser security mechanism that blocks JavaScript in one origin (e.g., dashboard.mybank.co.ke) from calling an API at a different origin (api.fraud.mybank.co.ke) unless the API explicitly allows it via Access-Control-Allow-Origin headers."),
        ("What is the difference between path parameters and query parameters?",
         "Path parameters identify a specific resource and are embedded in the URL path (e.g., /transactions/TXN-001). Query parameters filter or modify results and appear after ? (e.g., /transactions?status=flagged&limit=20)."),
        ("What is API versioning and how do you implement it?",
         "API versioning allows you to make breaking changes without affecting existing clients. Common approaches: URL versioning (/v1/transactions vs /v2/transactions), header versioning (Accept: application/vnd.api+json;version=2), and query param versioning (?version=2). URL versioning is most common and explicit."),
    ]
    for i, (q, a) in enumerate(iq_basic, 1):
        story += interview_q(i, q, a)

    story += H2("Section 2: FastAPI Specific (Q26-60)")
    iq_fastapi = [
        ("What makes FastAPI faster than Flask?",
         "FastAPI uses ASGI (Asynchronous Server Gateway Interface) and supports async/await natively, allowing concurrent handling of I/O-bound operations without blocking threads. Flask uses WSGI which is synchronous. FastAPI also uses Pydantic for validation, which is implemented in Rust for speed."),
        ("What is Pydantic and why does FastAPI use it?",
         "Pydantic is a data validation library that uses Python type hints. FastAPI uses it to automatically validate incoming request data, convert types, and generate OpenAPI documentation — all from your Python type annotations without extra code."),
        ("Explain FastAPI's Dependency Injection system.",
         "FastAPI's DI system, based on Depends(), automatically resolves and provides dependencies to route functions. It's used for database sessions, authentication, rate limiting, and shared logic. Dependencies can depend on other dependencies, forming a tree that FastAPI resolves automatically."),
        ("What is the difference between async def and def in FastAPI route handlers?",
         "async def enables asynchronous processing using Python's asyncio — useful when making I/O-bound operations like DB queries or HTTP calls without blocking other requests. def is synchronous — FastAPI runs it in a separate thread pool automatically. Use async def when using async libraries (asyncpg, httpx) and def when using blocking libraries (SQLAlchemy sync, requests)."),
        ("What is Pydantic's orm_mode (or model_config from_attributes)?",
         "orm_mode = True (Pydantic v1) or model_config = ConfigDict(from_attributes=True) (Pydantic v2) allows Pydantic models to read data from ORM objects (like SQLAlchemy model instances) in addition to regular dicts. FastAPI uses this when returning SQLAlchemy objects directly from route handlers."),
        ("How do you handle 422 Unprocessable Entity errors in FastAPI?",
         "FastAPI automatically returns 422 when Pydantic validation fails. You can customise the error handler using @app.exception_handler(RequestValidationError). The default response includes a 'detail' array listing every validation error with the field location, message, and type."),
        ("What is a response_model in FastAPI and why use it?",
         "response_model tells FastAPI what schema to use when serialising the response. It serves three purposes: (1) filters out fields not in the model (security — prevents leaking internal fields), (2) validates the response structure (catches bugs), and (3) generates accurate API documentation."),
        ("How does FastAPI generate API documentation automatically?",
         "FastAPI reads Python type hints, Pydantic model definitions, function docstrings, and decorator parameters to build an OpenAPI specification (JSON). Swagger UI reads this specification to render interactive docs at /docs, and ReDoc renders it at /redoc."),
        ("What is the purpose of status_code in FastAPI route decorators?",
         "It sets the default HTTP status code for successful responses. Common values: 200 for GET, 201 for POST (created), 204 for DELETE (no content). FastAPI uses this for documentation and the actual response — no need to manually set the status code in the function body for the happy path."),
        ("How do you protect a FastAPI endpoint so only authenticated users can access it?",
         "Create a dependency function that extracts and validates the JWT token (using OAuth2PasswordBearer and jose.jwt.decode). Add it to endpoints using Depends(get_current_user). FastAPI will call the dependency before the route function — if it raises HTTPException, the route never runs."),
    ]
    for i, (q, a) in enumerate(iq_fastapi, 26):
        story += interview_q(i, q, a)

    story += H2("Section 3: Databases and Security (Q61-80)")
    iq_db = [
        ("What is an ORM and what are its advantages?",
         "An ORM (Object-Relational Mapper) maps database tables to Python classes and rows to objects, allowing you to write Python code instead of SQL. Advantages: prevents SQL injection by default, makes code more readable and maintainable, and allows switching databases (SQLite in dev, PostgreSQL in prod) by changing one config value."),
        ("What is the N+1 query problem in SQLAlchemy?",
         "The N+1 problem occurs when you load a list of N objects and then make one additional query per object to load a relationship — resulting in N+1 total queries. Solve it with eager loading: db.query(Transaction).options(joinedload(Transaction.customer)).all() loads all customers in a single JOIN query."),
        ("Why should passwords never be stored in plain text?",
         "If the database is compromised, plain text passwords immediately give attackers access to all accounts, and also to any other service where users reused that password. Properly hashed passwords (using bcrypt, argon2) cannot be reversed, so even database exposure doesn't reveal the original passwords."),
        ("What is bcrypt and why use it for password hashing?",
         "bcrypt is a password hashing function designed to be computationally expensive (slow). It automatically incorporates a random 'salt', making rainbow table attacks ineffective. Its cost factor can be increased over time to stay ahead of faster hardware. This makes brute-force cracking impractical even if the database is leaked."),
        ("What is SQL injection and how does SQLAlchemy prevent it?",
         "SQL injection is an attack where malicious SQL code is inserted into user input to manipulate database queries. For example, username = ' OR '1'='1 could bypass login. SQLAlchemy uses parameterised queries by default — user inputs are always treated as data, never as SQL code. Never use string formatting to build SQL queries."),
        ("What is Alembic and why is it needed?",
         "Alembic is a database migration tool for SQLAlchemy. It tracks changes to your database schema over time and generates migration scripts. This allows you to evolve your schema (add columns, change types) while preserving existing data and keeping all environments (dev, staging, prod) in sync."),
        ("Explain the difference between SQLite and PostgreSQL for API development.",
         "SQLite is a file-based database — no server needed, perfect for development and testing. PostgreSQL is a production-grade client-server database with support for concurrent writes, advanced indexing, full-text search, and JSON columns. Always use SQLite for development/testing and PostgreSQL (or MySQL) for production."),
        ("What is connection pooling in databases?",
         "Connection pooling maintains a cache of database connections so they can be reused. Opening a new database connection is expensive (takes ~100ms). With pooling, connections are reused for multiple requests, dramatically improving performance. SQLAlchemy manages connection pools automatically."),
        ("What are environment variables and why must secrets be stored there?",
         "Environment variables are values set outside the application code, typically in .env files or the deployment platform's settings panel. Secrets (API keys, database passwords, JWT secret keys) must never be in source code because code is committed to Git (even private repos can be leaked). .env files should be in .gitignore."),
        ("What is the principle of least privilege in API security?",
         "Each user, service, or API key should have the minimum permissions necessary to perform its function. A read-only analyst account should not be able to delete transactions. A merchant's API key should only be able to submit transactions, not view other merchants' data. Enforced via role-based access control (RBAC)."),
    ]
    for i, (q, a) in enumerate(iq_db, 61):
        story += interview_q(i, q, a)

    story += H2("Section 4: System Design and Best Practices (Q81-100)")
    iq_system = [
        ("How would you implement rate limiting in a FastAPI fraud detection API?",
         "Use slowapi library (based on limits) or implement custom middleware. Store request counts in Redis with TTL. Rate limit by API key or IP address. Return 429 Too Many Requests with X-RateLimit-Remaining and Retry-After headers. Apply stricter limits to high-sensitivity endpoints like /transactions (POST)."),
        ("How do you handle versioning for an API that is already in production?",
         "Never break existing clients. Add new versions at new URLs (/v2/transactions) while keeping /v1 working. Deprecate old versions with a Deprecation: true header and sunset date. Document breaking changes clearly. Give clients at least 6 months notice before retiring a version."),
        ("What is the CAP theorem and how does it apply to fraud detection?",
         "CAP theorem: a distributed system can guarantee only two of three: Consistency (all nodes see the same data), Availability (every request gets a response), and Partition Tolerance (system works despite network splits). Fraud detection prioritises Consistency (we must not allow fraud due to stale data) and Partition Tolerance over availability. We'd rather block a transaction than approve fraudulent one."),
        ("How would you design the fraud detection API to handle 10,000 transactions per second?",
         "Async FastAPI with async database drivers (asyncpg). Read-heavy endpoints cached in Redis. Write transactions to a message queue (Kafka/SQS). Horizontal scaling behind a load balancer. Database read replicas for analytics queries. ML model served as a separate microservice with a connection pool. Auto-scaling based on request queue depth."),
        ("What is the difference between synchronous and asynchronous APIs?",
         "Synchronous: client waits for the response before continuing. Fast for real-time fraud scoring. Asynchronous: client submits a request and gets a 202 Accepted, then polls for results or receives a webhook. Better for long-running operations like batch fraud analysis or ML retraining. FastAPI supports both patterns."),
        ("Explain how you would implement audit logging for a fraud detection system.",
         "Log every request (timestamp, user, endpoint, IP), every fraud score generated (model version, features, score, decision), every manual override (who reviewed, what was changed, reason), and every authentication event (login, failure, token refresh). Store logs in a tamper-evident, append-only store. Required for regulatory compliance (CBK, GDPR)."),
        ("What is API gateway? When would you use one?",
         "An API gateway sits in front of your APIs and handles cross-cutting concerns: authentication, rate limiting, SSL termination, request routing, caching, and logging. Use one when you have multiple microservices (fraud API, customer API, merchant API) to avoid duplicating these concerns in every service. AWS API Gateway, Kong, and Nginx are common choices."),
        ("How would you implement webhook notifications for fraud events?",
         "Store webhook URLs registered by clients. When a fraud event occurs (score > threshold), use a background task to POST the event to the client's URL with HMAC-SHA256 signature verification (so the client can verify the payload came from you). Implement retry logic with exponential backoff for failed webhooks."),
        ("What monitoring and alerting would you set up for a production fraud API?",
         "Metrics: request rate, error rate (4xx/5xx), response time (p50/p95/p99), fraud score distribution, model prediction latency. Alerts: error rate > 1%, response time p95 > 500ms, model unavailable, unusual spike in CRITICAL transactions. Tools: Prometheus + Grafana, Datadog, AWS CloudWatch."),
        ("What is the difference between unit tests, integration tests, and end-to-end tests for an API?",
         "Unit tests test individual functions (e.g., test that extract_features() returns the correct shape). Integration tests test multiple components together (e.g., test that POST /transactions correctly writes to the database and returns the fraud score). End-to-end tests test the full system including external services (e.g., test the complete flow from transaction submission to SMS alert). FastAPI TestClient is used for integration tests."),
    ]
    for i, (q, a) in enumerate(iq_system, 81):
        story += interview_q(i, q, a)

    story += PBR()

    # ═══════════════════════════════════════════════
    # APPENDIX B — Quiz Questions
    # ═══════════════════════════════════════════════
    story += chapter_header("B", "100 Quiz Questions",
        "Test your knowledge — answers follow each question")

    story += H2("Quick-Fire Quiz: REST and HTTP")
    quizzes = [
        ("What does HTTP stand for?", "HyperText Transfer Protocol"),
        ("Which HTTP method is used to create a new resource?", "POST"),
        ("What status code means 'Not Found'?", "404"),
        ("What status code means 'Unauthorised'?", "401"),
        ("Which HTTP method is idempotent?", "GET, PUT, DELETE (all are idempotent)"),
        ("What does HTTPS add to HTTP?", "Encryption using TLS/SSL"),
        ("What does JSON stand for?", "JavaScript Object Notation"),
        ("What separates query parameters from the URL path?", "The ? character"),
        ("What HTTP method replaces an entire resource?", "PUT"),
        ("What HTTP method partially updates a resource?", "PATCH"),
        ("What does REST stand for?", "Representational State Transfer"),
        ("What is the standard port for HTTPS?", "443"),
        ("What format is used for API request bodies in FastAPI?", "JSON (application/json)"),
        ("What status code means 'OK' (successful GET)?", "200"),
        ("What status code means 'Created' (successful POST)?", "201"),
        ("What status code means 'No Content' (successful DELETE)?", "204"),
        ("What status code means 'Forbidden'?", "403"),
        ("What status code means 'Internal Server Error'?", "500"),
        ("What status code means 'Too Many Requests'?", "429"),
        ("What status code is returned when Pydantic validation fails in FastAPI?", "422"),
    ]
    for i, (q, a) in enumerate(quizzes, 1):
        story.append(Paragraph(f"<b>Q{i}:</b> {q}", ST["q_label"]))
        story.append(Paragraph(f"<b>A:</b> {a}", ST["qa"]))
        story += SP(4)

    story += H2("FastAPI Quiz (Q21-60)")
    fq = [
        ("What Python library does FastAPI use for data validation?", "Pydantic"),
        ("What ASGI server is typically used with FastAPI?", "Uvicorn"),
        ("What URL shows Swagger UI in FastAPI by default?", "/docs"),
        ("What URL shows ReDoc in FastAPI by default?", "/redoc"),
        ("What URL shows the OpenAPI JSON schema?", "/openapi.json"),
        ("What command runs a FastAPI app in development mode?", "uvicorn main:app --reload"),
        ("What decorator creates a GET endpoint in FastAPI?", "@app.get('/path')"),
        ("What class do Pydantic models inherit from?", "BaseModel"),
        ("What function is used to inject dependencies in FastAPI?", "Depends()"),
        ("What is the command to install FastAPI with all extras?", "pip install 'fastapi[all]'"),
        ("What does orm_mode = True enable in Pydantic?", "Reading data from SQLAlchemy ORM objects"),
        ("What parameter in Field() makes a field required?", "... (three dots, Ellipsis)"),
        ("What is the purpose of response_model in a route decorator?", "Filter and validate the response before sending to client"),
        ("How do you return a 201 status code in FastAPI?", "Add status_code=201 to the decorator"),
        ("What class handles OAuth2 bearer token extraction?", "OAuth2PasswordBearer"),
        ("What does @validator do in Pydantic?", "Defines a custom validation function for a specific field"),
        ("What does @root_validator do?", "Validates multiple fields together after individual field validation"),
        ("What is BackgroundTasks used for?", "Running functions after the HTTP response is sent"),
        ("What file format is used to define service orchestration?", "docker-compose.yml"),
        ("What is the purpose of --reload flag in uvicorn?", "Auto-restart the server when code changes (dev only)"),
    ]
    for i, (q, a) in enumerate(fq, 21):
        story.append(Paragraph(f"<b>Q{i}:</b> {q}", ST["q_label"]))
        story.append(Paragraph(f"<b>A:</b> {a}", ST["qa"]))
        story += SP(4)

    story += PBR()

    # ═══════════════════════════════════════════════
    # APPENDIX C — Coding Exercises
    # ═══════════════════════════════════════════════
    story += chapter_header("C", "50 Practical Coding Exercises",
        "Hands-on challenges to build real skills")

    exercises = [
        "Build a FastAPI app with a single GET endpoint that returns your name, the current date, and a message.",
        "Create a Pydantic model for a mobile money transaction with fields: amount (> 0), sender, receiver, currency (KES/USD/EUR only), and optional message.",
        "Add a POST /transactions endpoint that accepts the Pydantic model from Exercise 2 and returns it with a generated ID and timestamp.",
        "Add input validation: amount must be between 1 and 1,000,000. Return a custom 400 error if validation fails.",
        "Create a GET /transactions/{id} endpoint that returns a transaction from an in-memory dictionary. Return 404 if not found.",
        "Implement pagination for GET /transactions using page and limit query parameters. Default to page=1, limit=10.",
        "Add a PATCH /transactions/{id} endpoint that only updates the fields provided (do not overwrite unmodified fields).",
        "Add a DELETE /transactions/{id} endpoint. Return 204 on success, 404 if not found.",
        "Create a dependency function that validates an X-API-Key header. Return 401 if the key is missing or invalid.",
        "Implement password hashing using passlib. Write functions hash_password() and verify_password() with tests.",
        "Create a /auth/token endpoint that accepts username and password and returns a JWT token.",
        "Create a get_current_user dependency that validates a JWT token and returns the user's username and role.",
        "Protect the /transactions endpoints so only authenticated users can access them.",
        "Implement role-based access: only users with role='admin' can delete transactions.",
        "Connect FastAPI to SQLite using SQLAlchemy. Create a Transaction table with id, amount, customer_id, and timestamp.",
        "Refactor your POST /transactions endpoint to save transactions to the SQLite database.",
        "Refactor GET /transactions to read from the database with pagination.",
        "Implement a search filter: GET /transactions?customer_id=KE-001 returns only that customer's transactions.",
        "Add created_at and updated_at timestamps to the Transaction model, updated automatically.",
        "Write a pytest test for the POST /transactions endpoint that verifies a transaction is created and has a valid ID.",
        "Write a pytest test that verifies a 422 error is returned when amount is negative.",
        "Write a pytest test that verifies authentication is required (401 returned without token).",
        "Add middleware that logs the method, path, status code, and response time for every request.",
        "Add CORS middleware that allows requests from http://localhost:3000.",
        "Create a background task that prints a fraud alert to the console when fraud_score > 0.7.",
        "Create a simple rule-based fraud scorer: score += 0.4 for amount > 50000, 0.3 for hour < 6, 0.2 for new merchant.",
        "Integrate scikit-learn: train a Random Forest on synthetic data and save it with pickle.",
        "Load the saved ML model at startup (using a lifespan event) and expose it as a dependency.",
        "Create a /fraud-score endpoint that accepts transaction features and returns a fraud score from the ML model.",
        "Add a FraudLog SQLAlchemy model that records every fraud prediction made by the system.",
        "Implement Alembic: initialise it, create your first migration, and apply it to the database.",
        "Create a CSV file upload endpoint that parses transactions and returns a preview of the first 5 rows.",
        "Implement a /health endpoint that checks database connectivity and returns {status: healthy/degraded}.",
        "Add a /metrics endpoint that returns total transactions, total flagged, and average fraud score.",
        "Create a Dockerfile for your FastAPI app and verify it builds and runs correctly.",
        "Create a docker-compose.yml that runs FastAPI and PostgreSQL together.",
        "Switch your SQLAlchemy connection from SQLite to PostgreSQL using the docker-compose database.",
        "Implement a refresh token endpoint that issues a new access token given a valid refresh token.",
        "Add response caching: cache the /metrics endpoint for 60 seconds using a simple in-memory dict.",
        "Create an analytics endpoint GET /analytics/daily that returns transaction count and total amount grouped by day.",
        "Add a /customers/{id}/risk-profile endpoint that calculates a composite risk score from transaction history.",
        "Implement rate limiting: allow a maximum of 100 requests per minute per API key.",
        "Create a webhook simulation: POST /webhooks/register to save a URL, then trigger it when a transaction is flagged.",
        "Write a complete APIRouter for authentication (/auth/register, /auth/login, /auth/refresh, /auth/me).",
        "Add structured logging using Python's logging module. Log to both console and a transactions.log file.",
        "Implement a soft delete: instead of removing transactions, set is_deleted=True and filter them out in queries.",
        "Create a /admin/transactions endpoint that shows all transactions including soft-deleted ones (admin role only).",
        "Write a Python client script that registers a user, logs in, submits 10 transactions, and prints the fraud scores.",
        "Deploy your fraud detection API to Render.com and test the live /docs page.",
        "Extend the capstone project: add a merchant risk scoring endpoint that aggregates fraud scores for all transactions from a given merchant over the past 30 days.",
    ]
    story += exercise_box("All 50 Coding Exercises", exercises)
    story += PBR()

    # ═══════════════════════════════════════════════
    # APPENDIX D — Project Ideas
    # ═══════════════════════════════════════════════
    story += chapter_header("D", "20 Project Ideas",
        "Real-world projects to build and add to your portfolio")

    projects = [
        "<b>Real-Time Fraud Detection API</b> — Complete ML-powered fraud scoring API with transaction history, risk profiling, and analyst dashboard integration.",
        "<b>Mpesa Integration API</b> — FastAPI wrapper for Safaricom Daraja API with payment processing, C2B/B2C flows, and webhook handling.",
        "<b>Bank Reconciliation API</b> — API that accepts transaction files from multiple sources and identifies discrepancies.",
        "<b>Credit Scoring API</b> — ML model that scores loan applications based on transaction history and returns approve/reject decisions.",
        "<b>AML (Anti-Money Laundering) API</b> — System that identifies suspicious transaction patterns like structuring and layering.",
        "<b>KYC Verification API</b> — Know Your Customer API that verifies identity documents and returns verification status.",
        "<b>Chargeback Prediction API</b> — Predicts whether a transaction is likely to be disputed, allowing merchants to add friction.",
        "<b>Merchant Risk Profiling API</b> — Aggregates transaction data for merchants and produces dynamic risk scores.",
        "<b>Multi-Currency Transaction API</b> — Handles transactions across currencies with real-time exchange rate integration.",
        "<b>Notification Service API</b> — Event-driven API that sends SMS (Africastalking), email (SendGrid), and push notifications for fraud events.",
        "<b>Transaction Analytics API</b> — Provides fraud trend reports, peak fraud hours analysis, and geographic risk maps.",
        "<b>Account Takeover Detection API</b> — Detects unusual login patterns that suggest an account has been compromised.",
        "<b>Batch Fraud Screening API</b> — Accepts CSV files of thousands of transactions and returns fraud scores for each.",
        "<b>API Key Management Service</b> — Manages API keys for multiple clients with usage tracking and rate limiting.",
        "<b>Dispute Management API</b> — System for customers to report fraudulent transactions with evidence submission.",
        "<b>Audit Trail API</b> — Immutable log of all API actions for regulatory compliance.",
        "<b>Partner Integration Hub API</b> — API gateway that connects a bank's fraud system to multiple external data providers.",
        "<b>Card Control API</b> — Allows customers to freeze/unfreeze cards, set spend limits, and approve international transactions.",
        "<b>Synthetic Transaction Data Generator</b> — API that generates realistic test transaction data for fraud model training.",
        "<b>Federated Learning API</b> — Coordinate ML model training across multiple banks without sharing raw transaction data (privacy-preserving fraud detection).",
    ]
    for i, p in enumerate(projects, 1):
        story.append(Paragraph(f"{i}. {p}", ST["body"]))
        story += SP(4)
    story += PBR()

    # ═══════════════════════════════════════════════
    # APPENDIX E — Career Roadmap, Glossary, Cheat Sheets
    # ═══════════════════════════════════════════════
    story += chapter_header("E", "Career Roadmap, Glossary & Cheat Sheets",
        "Your guide from student to professional API engineer")

    story += H2("Career Roadmap: From Student to API Engineer")
    roadmap = [
        ("<b>Month 1-2: Foundations</b>", "Python basics, HTTP fundamentals, RESTful principles. Build 3 simple FastAPI apps without a database."),
        ("<b>Month 3-4: Core FastAPI</b>", "Pydantic validation, SQLAlchemy, authentication. Build the Fraud Detection API from Chapter 20."),
        ("<b>Month 5-6: Testing and DevOps</b>", "pytest, Docker, deployment to Render/Railway. Aim for 80%+ test coverage on your projects."),
        ("<b>Month 7-9: Advanced Topics</b>", "Async FastAPI, Redis caching, Celery background jobs, WebSockets. Study microservices architecture."),
        ("<b>Month 10-12: Production Skills</b>", "Kubernetes basics, CI/CD with GitHub Actions, monitoring with Prometheus/Grafana, API security (OWASP)."),
        ("<b>Year 2+: Specialisation</b>", "ML engineering integration, cloud-native development (AWS/GCP), system design, leadership skills."),
    ]
    for stage, desc in roadmap:
        story.append(Paragraph(f"{stage}: {desc}", ST["body"]))
        story += SP(6)

    story += H2("Glossary of Technical Terms")
    terms = [
        ("API", "Application Programming Interface — a defined way for software systems to communicate."),
        ("REST", "Representational State Transfer — an architectural style for distributed hypermedia systems."),
        ("FastAPI", "A modern Python web framework for building APIs, with automatic documentation."),
        ("Pydantic", "A Python data validation library that uses type hints."),
        ("JWT", "JSON Web Token — a compact, signed token for transmitting identity claims."),
        ("OAuth2", "An authorisation framework that enables third-party apps to obtain limited access."),
        ("ORM", "Object-Relational Mapper — maps database tables to Python classes."),
        ("SQLAlchemy", "A popular Python ORM and SQL toolkit."),
        ("Alembic", "A database migration tool for SQLAlchemy."),
        ("Uvicorn", "An ASGI web server for Python, used to run FastAPI apps."),
        ("ASGI", "Asynchronous Server Gateway Interface — the async successor to WSGI."),
        ("Middleware", "Code that runs before and after every HTTP request/response."),
        ("Dependency Injection", "A pattern where a component's dependencies are provided to it rather than created by it."),
        ("Idempotency", "An operation where multiple identical calls have the same effect as one call."),
        ("CORS", "Cross-Origin Resource Sharing — a browser security mechanism for cross-domain requests."),
        ("Fraud Score", "A number (0-1) indicating the probability that a transaction is fraudulent."),
        ("Feature Engineering", "Transforming raw data into numerical features that ML models can process."),
        ("Random Forest", "An ensemble ML model consisting of multiple decision trees."),
        ("bcrypt", "A password hashing algorithm designed to be computationally slow to resist brute force."),
        ("Rate Limiting", "Restricting the number of API calls a client can make in a given time period."),
        ("Webhook", "An HTTP callback — a server-to-server notification triggered by an event."),
        ("Docker", "A platform for packaging applications into portable containers."),
        ("Container", "A lightweight, isolated environment that packages code and its dependencies."),
        ("Microservice", "An architectural pattern where an application is split into small, independent services."),
        ("HATEOAS", "Hypermedia As The Engine Of Application State — REST responses include links to related actions."),
    ]
    for term, definition in terms:
        story += definition_box(term, definition)
        story += SP(3)

    story += H2("FastAPI Cheat Sheet")
    story += code_block([
        "# ─── INSTALLATION ───────────────────────────────────────",
        "pip install 'fastapi[all]'",
        "uvicorn main:app --reload",
        "",
        "# ─── BASIC STRUCTURE ────────────────────────────────────",
        "from fastapi import FastAPI",
        "app = FastAPI(title='My API', version='1.0.0')",
        "",
        "# ─── HTTP METHODS ───────────────────────────────────────",
        "@app.get('/resource')               # Read all",
        "@app.get('/resource/{id}')          # Read one",
        "@app.post('/resource')              # Create",
        "@app.put('/resource/{id}')          # Replace",
        "@app.patch('/resource/{id}')        # Partial update",
        "@app.delete('/resource/{id}')       # Delete",
        "",
        "# ─── PYDANTIC MODEL ─────────────────────────────────────",
        "from pydantic import BaseModel, Field",
        "class MyModel(BaseModel):",
        "    name: str = Field(..., min_length=2)",
        "    amount: float = Field(..., gt=0)",
        "    optional_note: str | None = None",
        "",
        "# ─── PATH / QUERY PARAMS ────────────────────────────────",
        "@app.get('/items/{item_id}')         # Path param",
        "def read(item_id: int, q: str = None): ...",
        "",
        "# ─── STATUS CODES ───────────────────────────────────────",
        "@app.post('/items', status_code=201)",
        "@app.delete('/items/{id}', status_code=204)",
        "",
        "# ─── ERROR HANDLING ─────────────────────────────────────",
        "from fastapi import HTTPException",
        "raise HTTPException(status_code=404, detail='Not found')",
        "",
        "# ─── DEPENDENCY INJECTION ───────────────────────────────",
        "from fastapi import Depends",
        "def my_dep() -> str: return 'value'",
        "@app.get('/protected')",
        "def route(val: str = Depends(my_dep)): ...",
        "",
        "# ─── JWT AUTH ────────────────────────────────────────────",
        "from fastapi.security import OAuth2PasswordBearer",
        "oauth2 = OAuth2PasswordBearer(tokenUrl='auth/token')",
        "token: str = Depends(oauth2)",
        "",
        "# ─── DATABASE SESSION ────────────────────────────────────",
        "def get_db(): yield SessionLocal()",
        "db: Session = Depends(get_db)",
        "",
        "# ─── BACKGROUND TASKS ────────────────────────────────────",
        "from fastapi import BackgroundTasks",
        "def route(bg: BackgroundTasks):",
        "    bg.add_task(my_function, arg1, arg2)",
        "",
        "# ─── ROUTERS ─────────────────────────────────────────────",
        "from fastapi import APIRouter",
        "router = APIRouter(prefix='/transactions', tags=['Transactions'])",
        "app.include_router(router)",
        "",
        "# ─── TESTING ─────────────────────────────────────────────",
        "from fastapi.testclient import TestClient",
        "client = TestClient(app)",
        "response = client.get('/endpoint')",
        "assert response.status_code == 200",
    ])

    story += H2("REST API Best Practices")
    best_practices = [
        "Always version your API: /v1/transactions, /v2/transactions",
        "Use nouns for resource names: /transactions not /getTransactions",
        "Use plural nouns: /transactions not /transaction",
        "Return meaningful HTTP status codes — never return 200 for an error",
        "Include pagination for all collection endpoints",
        "Use HTTPS in production — never expose APIs over plain HTTP",
        "Never return plain passwords or sensitive internal fields in API responses",
        "Validate all input with Pydantic — never trust client data",
        "Return structured error responses with error codes and descriptive messages",
        "Rate limit all endpoints, with stricter limits on authentication endpoints",
        "Log all API access with timestamps, user IDs, and response times",
        "Document every endpoint with descriptions, examples, and error responses",
        "Use environment variables for all secrets — never commit them to Git",
        "Implement health check (/health) and metrics (/metrics) endpoints",
        "Always test authentication, validation, and edge cases before deploying",
    ]
    for i, p in enumerate(best_practices, 1):
        story.append(Paragraph(f"{i}. {p}", ST["body"]))
        story += SP(4)

    story += H2("Security Best Practices")
    sec = [
        "Use HTTPS with TLS 1.2+ — never plain HTTP in production",
        "Hash passwords with bcrypt or argon2 — never MD5, SHA1, or plain text",
        "Set JWT expiration times — 15 minutes for access tokens, 7 days for refresh tokens",
        "Store the JWT secret key only in environment variables, never in source code",
        "Validate and sanitise ALL user input — assume every input is malicious",
        "Use parameterised queries (SQLAlchemy default) — never build SQL with string formatting",
        "Implement rate limiting on authentication endpoints (max 5 failed logins per 15 minutes)",
        "Use CORS to restrict API access to trusted origins only",
        "Set security headers: X-Content-Type-Options, X-Frame-Options, Strict-Transport-Security",
        "Implement input size limits — reject excessively large request bodies",
        "Audit log all authentication events and sensitive operations",
        "Rotate secrets regularly — API keys, JWT secrets, database passwords",
        "Implement API key scopes — a read-only key cannot submit transactions",
        "Use principle of least privilege for database users — API user should not have DROP TABLE permission",
        "Scan dependencies for vulnerabilities: pip install safety; safety check",
    ]
    for i, p in enumerate(sec, 1):
        story.append(Paragraph(f"{i}. {p}", ST["body"]))
        story += SP(4)

    story += H2("Performance Optimisation Techniques")
    perf = [
        "Use async/await for I/O-bound operations (database queries, external API calls)",
        "Cache frequently-read data in Redis (e.g., ML model configuration, merchant blacklists)",
        "Use database connection pooling — never create a new connection per request",
        "Add database indexes on frequently-filtered columns (customer_id, transaction_id, created_at)",
        "Implement pagination — never return unlimited rows from the database",
        "Use eager loading (joinedload) to avoid N+1 query problems",
        "Stream large file downloads instead of loading them all into memory",
        "Use background tasks for non-critical work (notifications, logging to slow stores)",
        "Profile slow endpoints with time.time() or APM tools before optimising",
        "Use database query EXPLAIN to identify slow queries and missing indexes",
    ]
    for i, p in enumerate(perf, 1):
        story.append(Paragraph(f"{i}. {p}", ST["body"]))
        story += SP(4)

    story += H2("Further Reading")
    reading = [
        "<b>Official FastAPI Documentation</b> — fastapi.tiangolo.com — The most comprehensive source for FastAPI",
        "<b>Pydantic Documentation</b> — docs.pydantic.dev",
        "<b>SQLAlchemy Documentation</b> — docs.sqlalchemy.org",
        "<b>Building Microservices (O'Reilly)</b> — Sam Newman — System design for service-based architectures",
        "<b>Designing Data-Intensive Applications</b> — Martin Kleppmann — Essential for understanding scalability",
        "<b>OWASP API Security Top 10</b> — owasp.org — Critical security vulnerabilities to avoid",
        "<b>REST API Design Rulebook (O'Reilly)</b> — Mark Masse — Deep dive into REST principles",
        "<b>Hands-On Machine Learning (O'Reilly)</b> — Aurelien Geron — ML foundations for fraud detection",
        "<b>Scikit-learn Documentation</b> — scikit-learn.org — For fraud detection model development",
    ]
    for r in reading:
        story.append(Paragraph(f"• {r}", ST["bullet"]))
        story += SP(4)

    # ── FINAL PAGE ─────────────────────────────────────────────────
    story += PBR()
    story.append(Spacer(1, 3*cm))
    final_table = Table([[
        Paragraph("REST APIs &amp; FastAPI — Complete Professional Study Guide", ST["cover_title"])
    ]], colWidths=["100%"],
    style=TableStyle([("BACKGROUND",(0,0),(-1,-1),DARK_BLUE),
                      ("TOPPADDING",(0,0),(-1,-1),30),
                      ("BOTTOMPADDING",(0,0),(-1,-1),30)]))
    story.append(final_table)
    story.append(Spacer(1, 1*cm))
    story.append(Paragraph("This guide covered 20 chapters, from HTTP fundamentals to a complete production fraud detection system.", ST["cover_info"]))
    story.append(Paragraph("100 interview questions • 100 quiz questions • 50 coding exercises • 20 project ideas", ST["cover_info"]))
    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph(f"Generated {datetime.date.today().strftime('%B %Y')} — Edition 1.0", ST["cover_info"]))

    return story


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE TEMPLATE WITH HEADER / FOOTER
# ═══════════════════════════════════════════════════════════════════════════════

def build_pdf(output_path: str):
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=2*cm,
        leftMargin=2*cm,
        topMargin=2.5*cm,
        bottomMargin=2*cm,
    )

    def on_page(canvas, doc):
        canvas.saveState()
        page_num = doc.page
        w, h = A4

        # Header bar
        canvas.setFillColor(DARK_BLUE)
        canvas.rect(0, h - 1.5*cm, w, 1.5*cm, fill=1, stroke=0)
        canvas.setFillColor(WHITE)
        canvas.setFont("Helvetica-Bold", 9)
        canvas.drawString(2*cm, h - 1*cm, "REST APIs & FastAPI — Complete Study Guide")
        canvas.setFont("Helvetica", 8)
        canvas.drawRightString(w - 2*cm, h - 1*cm, "For Software Engineering & ML Engineering Students")

        # Footer bar
        canvas.setFillColor(DARK_BLUE)
        canvas.rect(0, 0, w, 1.2*cm, fill=1, stroke=0)
        canvas.setFillColor(ACCENT)
        canvas.setFont("Helvetica-Bold", 9)
        canvas.drawCentredString(w/2, 0.4*cm, f"Page {page_num}")
        canvas.setFillColor(GREY_MID)
        canvas.setFont("Helvetica", 8)
        canvas.drawString(2*cm, 0.4*cm, "fraud-detection-api.dev")
        canvas.drawRightString(w - 2*cm, 0.4*cm, "FastAPI | Pydantic | SQLAlchemy | JWT | Docker")

        canvas.restoreState()

    story = build_content()
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    print(f"PDF generated: {output_path}")

if __name__ == "__main__":
    build_pdf("/mnt/user-data/outputs/REST_APIs_and_FastAPI_Complete_Study_Guide.pdf")
