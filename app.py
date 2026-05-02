import os
import re
import time
import random
import smtplib
from email.mime.text import MIMEText
from functools import wraps

import bcrypt
import psycopg2
import requests
from flask import Flask, jsonify, redirect, render_template, request, session, url_for

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key")

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")

ALLOWED_DOMAINS = ("@gmail.com", "@outlook.com", "@gla.ac.in")
OTP_EXPIRY_SECONDS = 10 * 60


def get_connection():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL environment variable is missing")
    return psycopg2.connect(db_url, sslmode="require")


def create_tables():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("DATABASE_URL not found. Skipping table creation.")
        return

    try:
        conn = get_connection()
        cur = conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100),
                username VARCHAR(80) UNIQUE,
                email VARCHAR(150) UNIQUE NOT NULL,
                phone VARCHAR(20),
                password TEXT,
                is_verified BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS name VARCHAR(100);")
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS username VARCHAR(80);")
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS phone VARCHAR(20);")
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS password TEXT;")
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_verified BOOLEAN DEFAULT TRUE;")
        cur.execute("UPDATE users SET is_verified = TRUE WHERE is_verified IS NULL;")

        # Username uniqueness is checked in Python before insert also.
        # This index may already exist from your previous version.
        try:
            cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS users_username_unique ON users (username);")
        except Exception as idx_error:
            print("Username unique index warning:", idx_error)
            conn.rollback()
            conn = get_connection()
            cur = conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS history (
                id SERIAL PRIMARY KEY,
                user_id INT REFERENCES users(id) ON DELETE CASCADE,
                action VARCHAR(50),
                input_text TEXT,
                output_text TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        conn.commit()
        cur.close()
        conn.close()
        print("Database tables ready.")

    except Exception as e:
        print("Database table creation error:", e)


create_tables()


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            if request.path.startswith((
                "/generate",
                "/correct",
                "/enhance",
                "/topic",
                "/regenerate",
                "/professional",
                "/plagiarism",
                "/wordcount"
            )):
                return jsonify({"status": "fail", "message": "Please login first"}), 401

            return redirect(url_for("login_page"))

        return fn(*args, **kwargs)

    return wrapper


def valid_email(email):
    email = (email or "").strip().lower()
    return bool(email) and email.endswith(ALLOWED_DOMAINS)


def clean_username(username):
    return re.sub(r"[^a-zA-Z0-9_]", "", (username or "").strip().lower())


def clean_phone(phone):
    phone = re.sub(r"\D", "", (phone or "").strip())

    if len(phone) == 12 and phone.startswith("91"):
        phone = phone[2:]

    if len(phone) == 11 and phone.startswith("0"):
        phone = phone[1:]

    return phone


def validate_email_only(email):
    email = (email or "").strip().lower()

    if not valid_email(email):
        return None, "Use Gmail, Outlook, or GLA email only"

    return email, None


def validate_email_signup_payload(data, verified_email):
    username = clean_username(data.get("username"))
    email = (data.get("email") or "").strip().lower()
    phone = clean_phone(data.get("phone"))
    password = data.get("password") or ""
    confirm_password = data.get("confirm_password") or data.get("recheck_password") or ""
    accepted_terms = bool(data.get("accepted_terms"))

    if not verified_email:
        return None, "Please verify your email OTP first"

    if email != verified_email:
        return None, "Email changed. Please verify OTP again."

    if len(username) < 3 or len(username) > 30:
        return None, "Username must be 3 to 30 characters"

    if not valid_email(email):
        return None, "Use Gmail, Outlook, or GLA email only"

    if phone and len(phone) != 10:
        return None, "Enter a valid 10-digit mobile number or keep it blank"

    if len(password) < 6:
        return None, "Password must be at least 6 characters"

    if password != confirm_password:
        return None, "Password and recheck password do not match"

    if not accepted_terms:
        return None, "Please accept Terms & Privacy to continue"

    return {
        "name": username,
        "username": username,
        "email": email,
        "phone": phone,
        "password": password,
    }, None


def username_exists(cur, username):
    cur.execute("SELECT id FROM users WHERE username = %s", (username,))
    return cur.fetchone() is not None


def generate_unique_username(cur, email):
    base = clean_username(email.split("@")[0]) or "user"
    base = base[:22]
    username = base
    counter = 1

    while username_exists(cur, username):
        username = f"{base}{counter}"
        counter += 1

    return username


def send_otp_email(receiver_email, otp):
    """
    Sends OTP using Postmark Email API over HTTPS.
    This works on Render Free because it does not use blocked SMTP ports.
    Required Render Environment Variables:
        POSTMARK_SERVER_TOKEN
        POSTMARK_FROM_EMAIL
    """

    postmark_token = os.environ.get("POSTMARK_SERVER_TOKEN", "").strip()
    from_email = os.environ.get("POSTMARK_FROM_EMAIL", "").strip()

    subject = "Your AI.CREATIVE verification OTP"
    body = f"""
Hello,

Your OTP for AI.CREATIVE account verification is: {otp}

This OTP is valid for 10 minutes. Do not share it with anyone.

Regards,
AI.CREATIVE Team
""".strip()

    if not postmark_token or not from_email:
        print(f"OTP for {receiver_email}: {otp}")
        return True, "OTP generated. POSTMARK_SERVER_TOKEN or POSTMARK_FROM_EMAIL is missing, so check Render logs for demo OTP.", True

    try:
        response = requests.post(
            "https://api.postmarkapp.com/email",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-Postmark-Server-Token": postmark_token,
            },
            json={
                "From": from_email,
                "To": receiver_email,
                "Subject": subject,
                "TextBody": body,
                "MessageStream": "outbound",
            },
            timeout=20,
        )

        try:
            data = response.json()
        except Exception:
            data = {"raw": response.text[:300]}

        print("Postmark API response:", response.status_code, data)

        if response.status_code == 200 and data.get("ErrorCode", 0) == 0:
            return True, "OTP sent successfully. Check your email inbox.", False

        error_message = data.get("Message") or data.get("message") or str(data)
        return False, f"OTP email failed: {error_message}", False

    except requests.exceptions.Timeout:
        return False, "OTP email request timed out. Try again.", False

    except Exception as e:
        print("Postmark OTP email error:", e)
        return False, "OTP email failed. Check POSTMARK_SERVER_TOKEN, POSTMARK_FROM_EMAIL, and Render logs.", False


def demo_ai_response(prompt, mode="generate"):
    clean = " ".join(str(prompt).split())[:700]

    if mode == "topic":
        return (
            "AI Creative Writing Platform is a smart writing assistant that helps users generate ideas, "
            "improve drafts, correct grammar, and polish content while keeping the user's original voice. "
            "It supports students, bloggers, and creators by making writing faster, clearer, and more professional."
        )

    if mode == "correct":
        return "Corrected version: " + clean.replace(" i ", " I ")

    if mode == "enhance":
        return (
            "Enhanced version: "
            + clean
            + "\n\nThis version is clearer, more polished, and presentation-friendly."
        )

    if mode == "professional":
        return (
            "Professional Score: 8/10. The writing is clear and understandable. "
            "It can be improved with more formal word choice and tighter sentence structure."
        )

    if mode == "plagiarism":
        return (
            "Originality Estimate: 85%. This appears mostly original, but important academic/project "
            "content should still be checked with a proper plagiarism tool."
        )

    return "Generated version: " + clean


def call_ai(prompt, mode="generate"):
    if not GROQ_API_KEY:
        return demo_ai_response(prompt, mode)

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "You are a helpful AI writing assistant. Give clean, useful, plagiarism-safe writing support.",
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        "temperature": 0.7,
    }

    try:
        response = requests.post(
            GROQ_API_URL,
            headers=headers,
            json=payload,
            timeout=30
        )

        data = response.json()

        if response.status_code != 200:
            print("Groq API error:", response.status_code, data)
            return demo_ai_response(prompt, mode)

        return data["choices"][0]["message"]["content"].strip()

    except Exception as e:
        print("AI request failed:", e)
        return demo_ai_response(prompt, mode)


def save_history(action, input_text, output_text):
    if "user_id" not in session:
        return

    try:
        conn = get_connection()
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO history (user_id, action, input_text, output_text)
            VALUES (%s, %s, %s, %s)
            """,
            (session["user_id"], action, input_text, output_text),
        )

        conn.commit()
        cur.close()
        conn.close()

    except Exception as e:
        print("History save error:", e)


@app.route("/")
def landing_page():
    if "user_id" in session:
        return redirect(url_for("index"))

    return render_template("landing.html")


@app.route("/auth")
def login_page():
    if "user_id" in session:
        return redirect(url_for("index"))

    return render_template("login.html")


@app.route("/index")
@login_required
def index():
    user_name = "User"

    try:
        conn = get_connection()
        cur = conn.cursor()

        cur.execute("SELECT name FROM users WHERE id = %s", (session["user_id"],))
        row = cur.fetchone()

        if row and row[0]:
            user_name = row[0]

        cur.close()
        conn.close()

    except Exception as e:
        print("User name fetch error:", e)

    return render_template(
        "index.html",
        user_name=user_name,
        user_id=session["user_id"]
    )


@app.route("/send-otp", methods=["POST"])
def send_otp():
    data = request.get_json(silent=True) or {}
    email, error = validate_email_only(data.get("email"))

    if error:
        return jsonify({
            "status": "fail",
            "message": error
        })

    try:
        conn = get_connection()
        cur = conn.cursor()

        cur.execute("SELECT id FROM users WHERE email = %s", (email,))
        existing_user = cur.fetchone()

        cur.close()
        conn.close()

        if existing_user:
            return jsonify({
                "status": "fail",
                "message": "This email is already registered. Please login with your username."
            })

        otp = str(random.SystemRandom().randint(100000, 999999))

        session["pending_signup_email"] = email
        session["pending_signup_otp"] = otp
        session["pending_signup_time"] = time.time()
        session.pop("verified_signup_email", None)

        sent, message, demo_mode = send_otp_email(email, otp)

        if not sent:
            return jsonify({
                "status": "fail",
                "message": message
            })

        response = {
            "status": "success",
            "message": message
        }

        if demo_mode:
            response["demo_otp"] = otp

        return jsonify(response)

    except Exception as e:
        print("Send email OTP error:", e)
        return jsonify({
            "status": "fail",
            "message": "OTP failed. Check database/Postmark settings."
        })


@app.route("/verify-otp", methods=["POST"])
def verify_otp():
    data = request.get_json(silent=True) or {}
    email, error = validate_email_only(data.get("email"))
    otp = (data.get("otp") or "").strip()

    if error:
        return jsonify({
            "status": "fail",
            "message": error
        })

    if not otp:
        return jsonify({
            "status": "fail",
            "message": "OTP is required"
        })

    pending_email = session.get("pending_signup_email")
    saved_otp = session.get("pending_signup_otp")
    pending_time = session.get("pending_signup_time")

    if not pending_email or not saved_otp or not pending_time:
        return jsonify({
            "status": "fail",
            "message": "Please send OTP first"
        })

    if pending_email != email:
        return jsonify({
            "status": "fail",
            "message": "Email changed. Please send OTP again."
        })

    if time.time() - float(pending_time) > OTP_EXPIRY_SECONDS:
        session.pop("pending_signup_email", None)
        session.pop("pending_signup_otp", None)
        session.pop("pending_signup_time", None)
        session.pop("verified_signup_email", None)

        return jsonify({
            "status": "fail",
            "message": "OTP expired. Send a new OTP."
        })

    if otp != saved_otp:
        return jsonify({
            "status": "fail",
            "message": "Invalid OTP"
        })

    session["verified_signup_email"] = email
    session.pop("pending_signup_otp", None)

    return jsonify({
        "status": "success",
        "message": "Email verified. Now create your username and password."
    })


@app.route("/complete-signup", methods=["POST"])
def complete_signup():
    data = request.get_json(silent=True) or {}
    verified_email = session.get("verified_signup_email")

    payload, error = validate_email_signup_payload(data, verified_email)

    if error:
        return jsonify({
            "status": "fail",
            "message": error
        })

    try:
        conn = get_connection()
        cur = conn.cursor()

        if payload["phone"]:
            cur.execute(
                "SELECT id FROM users WHERE email = %s OR username = %s OR phone = %s",
                (payload["email"], payload["username"], payload["phone"])
            )
        else:
            cur.execute(
                "SELECT id FROM users WHERE email = %s OR username = %s",
                (payload["email"], payload["username"])
            )

        existing_user = cur.fetchone()

        if existing_user:
            cur.close()
            conn.close()

            return jsonify({
                "status": "fail",
                "message": "Email, username, or mobile number already exists."
            })

        hashed_password = bcrypt.hashpw(
            payload["password"].encode("utf-8"),
            bcrypt.gensalt(rounds=10)
        ).decode("utf-8")

        cur.execute(
            """
            INSERT INTO users (name, username, email, phone, password, is_verified)
            VALUES (%s, %s, %s, %s, %s, TRUE)
            """,
            (
                payload["name"],
                payload["username"],
                payload["email"],
                payload["phone"],
                hashed_password,
            ),
        )

        conn.commit()
        cur.close()
        conn.close()

        session.pop("pending_signup_email", None)
        session.pop("pending_signup_otp", None)
        session.pop("pending_signup_time", None)
        session.pop("verified_signup_email", None)

        return jsonify({
            "status": "success",
            "message": "Account created successfully. Login with your username.",
            "username": payload["username"]
        })

    except Exception as e:
        print("Complete email signup error:", e)

        return jsonify({
            "status": "fail",
            "message": "Signup failed. Check database connection."
        })


@app.route("/signup", methods=["POST"])
def signup():
    return complete_signup()


@app.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}

    login_id = (
        data.get("login_id")
        or data.get("email")
        or data.get("username")
        or ""
    ).strip().lower()
    password = data.get("password") or ""

    if not login_id or not password:
        return jsonify({
            "status": "fail",
            "message": "Username/email and password are required"
        })

    try:
        conn = get_connection()
        cur = conn.cursor()

        cur.execute(
            """
            SELECT id, password, COALESCE(is_verified, TRUE)
            FROM users
            WHERE LOWER(email) = %s OR LOWER(username) = %s
            """,
            (login_id, login_id)
        )

        user = cur.fetchone()

        cur.close()
        conn.close()

        if not user:
            return jsonify({
                "status": "fail",
                "message": "No account found with this username/email"
            })

        user_id, stored_password, is_verified = user

        if not is_verified:
            return jsonify({
                "status": "fail",
                "message": "Please verify your email before login"
            })

        if not stored_password:
            return jsonify({
                "status": "fail",
                "message": "Password not found for this account. Please create a username-password account."
            })

        if bcrypt.checkpw(password.encode("utf-8"), stored_password.encode("utf-8")):
            session["user_id"] = user_id

            return jsonify({
                "status": "success"
            })

        return jsonify({
            "status": "fail",
            "message": "Invalid password"
        })

    except Exception as e:
        print("Login error:", e)

        return jsonify({
            "status": "fail",
            "message": "Login failed. Check database connection."
        })


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing_page"))


@app.route("/generate", methods=["POST"])
@login_required
def generate():
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()

    if not text:
        return jsonify({
            "result": "Please enter text first."
        })

    prompt = f"Rewrite this text clearly and naturally while preserving meaning:\n\n{text}"

    result = call_ai(prompt, "generate")
    save_history("generate", text, result)

    return jsonify({
        "result": result
    })


@app.route("/correct", methods=["POST"])
@login_required
def correct():
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()

    if not text:
        return jsonify({
            "result": "Please enter text first."
        })

    prompt = f"Correct grammar, punctuation, and spelling only. Keep the original meaning:\n\n{text}"

    result = call_ai(prompt, "correct")
    save_history("correct", text, result)

    return jsonify({
        "result": result
    })


@app.route("/enhance", methods=["POST"])
@login_required
def enhance():
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()

    if not text:
        return jsonify({
            "result": "Please enter text first."
        })

    prompt = f"Enhance this writing. Make it creative, polished, clear, and presentation-friendly:\n\n{text}"

    result = call_ai(prompt, "enhance")
    save_history("enhance", text, result)

    return jsonify({
        "result": result
    })


@app.route("/topic", methods=["POST"])
@login_required
def topic():
    data = request.get_json(silent=True) or {}

    topic_text = (data.get("topic") or "").strip()
    length = (data.get("length") or "short").strip().lower()

    if not topic_text:
        return jsonify({
            "result": "Please enter a topic first."
        })

    prompt = f"Write a {length} creative, original, and professional description about: {topic_text}"

    result = call_ai(prompt, "topic")
    save_history("topic", topic_text, result)

    return jsonify({
        "result": result
    })


@app.route("/regenerate", methods=["POST"])
@login_required
def regenerate():
    data = request.get_json(silent=True) or {}

    original = (data.get("original") or "").strip()
    feedback = (data.get("feedback") or "").strip()

    if not original or not feedback:
        return jsonify({
            "result": "Generate content and write feedback first."
        })

    prompt = f"""
Rewrite the following AI-generated text according to the user's feedback.

Original text:
{original}

User feedback:
{feedback}
"""

    result = call_ai(prompt, "generate")
    save_history("regenerate", feedback, result)

    return jsonify({
        "result": result
    })


@app.route("/wordcount", methods=["POST"])
@login_required
def wordcount():
    data = request.get_json(silent=True) or {}

    text = data.get("text") or ""

    return jsonify({
        "words": len(text.split()),
        "characters": len(text)
    })


@app.route("/professional", methods=["POST"])
@login_required
def professional():
    data = request.get_json(silent=True) or {}

    text = (data.get("text") or "").strip()

    if not text:
        return jsonify({
            "result": "Please enter text first."
        })

    prompt = f"Give a professionalism score out of 10 and 2-3 short improvement tips for this text:\n\n{text}"

    result = call_ai(prompt, "professional")
    save_history("professional", text, result)

    return jsonify({
        "result": result
    })


@app.route("/plagiarism", methods=["POST"])
@login_required
def plagiarism():
    data = request.get_json(silent=True) or {}

    text = (data.get("text") or "").strip()

    if not text:
        return jsonify({
            "result": "Please enter text first."
        })

    prompt = f"Estimate originality/plagiarism risk for this text. Give originality percentage and brief explanation. Do not claim it is a real plagiarism scan:\n\n{text}"

    result = call_ai(prompt, "plagiarism")
    save_history("plagiarism", text, result)

    return jsonify({
        "result": result
    })


@app.route("/health")
def health():
    return jsonify({
        "status": "ok"
    })


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=True
    )
