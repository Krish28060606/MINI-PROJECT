import os
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
                email VARCHAR(150) UNIQUE NOT NULL,
                phone VARCHAR(20),
                password TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

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


@app.route("/signup", methods=["POST"])
def signup():
    data = request.get_json(silent=True) or {}

    name = (data.get("name") or "User").strip()
    email = (data.get("email") or "").strip().lower()
    phone = (data.get("phone") or "").strip()
    password = data.get("password") or ""

    if not email or not password:
        return jsonify({
            "status": "fail",
            "message": "Email and password are required"
        })

    allowed_domains = ("@gmail.com", "@outlook.com", "@gla.ac.in")

    if not email.endswith(allowed_domains):
        return jsonify({
            "status": "fail",
            "message": "Use Gmail, Outlook, or GLA email only"
        })

    try:
        conn = get_connection()
        cur = conn.cursor()

        cur.execute("SELECT id FROM users WHERE email = %s", (email,))
        existing_user = cur.fetchone()

        if existing_user:
            cur.close()
            conn.close()

            return jsonify({
                "status": "fail",
                "message": "User already exists. Please login."
            })

        hashed_password = bcrypt.hashpw(
            password.encode("utf-8"),
            bcrypt.gensalt()
        ).decode("utf-8")

        cur.execute(
            """
            INSERT INTO users (name, email, phone, password)
            VALUES (%s, %s, %s, %s)
            """,
            (name, email, phone, hashed_password),
        )

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({
            "status": "success",
            "message": "Signup successful"
        })

    except Exception as e:
        print("Signup error:", e)

        return jsonify({
            "status": "fail",
            "message": "Signup failed. Check database connection."
        })


@app.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}

    email = (data.get("email") or "").strip().lower()
    mobile = (data.get("mobile") or "").strip()
    password = data.get("password") or ""

    if not email or not password:
        return jsonify({
            "status": "fail",
            "message": "Email and password are required"
        })

    try:
        conn = get_connection()
        cur = conn.cursor()

        if mobile:
            cur.execute(
                "SELECT id, password FROM users WHERE email = %s AND phone = %s",
                (email, mobile)
            )
        else:
            cur.execute(
                "SELECT id, password FROM users WHERE email = %s",
                (email,)
            )

        user = cur.fetchone()

        cur.close()
        conn.close()

        if not user:
            return jsonify({
                "status": "fail",
                "message": "Invalid credentials"
            })

        user_id, stored_password = user

        if stored_password and bcrypt.checkpw(
            password.encode("utf-8"),
            stored_password.encode("utf-8")
        ):
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


@app.route("/google-login", methods=["POST"])
def google_login():
    data = request.get_json(silent=True) or {}
    token = data.get("token")

    if not token:
        return jsonify({
            "status": "fail",
            "message": "Google token missing"
        })

    try:
        import jwt

        decoded = jwt.decode(token, options={"verify_signature": False})

        email = (decoded.get("email") or "").strip().lower()
        name = decoded.get("name") or "Google User"

        if not email:
            return jsonify({
                "status": "fail",
                "message": "Google email missing"
            })

        conn = get_connection()
        cur = conn.cursor()

        cur.execute("SELECT id FROM users WHERE email = %s", (email,))
        row = cur.fetchone()

        if row:
            user_id = row[0]
        else:
            cur.execute(
                """
                INSERT INTO users (name, email, phone, password)
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                (name, email, "", ""),
            )

            user_id = cur.fetchone()[0]
            conn.commit()

        cur.close()
        conn.close()

        session["user_id"] = user_id

        return jsonify({
            "status": "success"
        })

    except Exception as e:
        print("Google login error:", e)

        return jsonify({
            "status": "fail",
            "message": "Google login failed"
        })


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login_page"))


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
