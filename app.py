from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import requests
import bcrypt
from db import get_connection
from google.oauth2 import id_token
from google.auth.transport import requests as grequests
import jwt
import os
import psycopg2

def create_tables():
    db_url = os.environ.get("DATABASE_URL")

    if not db_url:
        print("DATABASE_URL not found. Skipping table creation locally.")
        return

    conn = psycopg2.connect(db_url, sslmode="require")
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        name VARCHAR(100),
        email VARCHAR(100) UNIQUE,
        phone VARCHAR(20),
        password TEXT
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

create_tables()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "fallback-secret")


# ------------------------
# GROQ API
# ------------------------

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
API_URL = "https://api.groq.com/openai/v1/chat/completions"

headers = {
    "Authorization": f"Bearer {GROQ_API_KEY}",
    "Content-Type": "application/json"
}


def call_ai(prompt):

    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "user", "content": prompt}
        ]
    }

    try:
        response = requests.post(API_URL, headers=headers, json=payload)
        result = response.json()

        if "choices" not in result:
            return "AI service error"

        return result["choices"][0]["message"]["content"]

    except Exception as e:
        return "AI request failed"


# ------------------------
# LOGIN PAGE
# ------------------------

@app.route("/")
def login_page():
    return render_template("login.html")


# ------------------------
# INDEX PAGE
# ------------------------

@app.route("/index")
def index():

    if "user_id" not in session:
        return redirect(url_for("login_page"))

    user_name = None

    try:
        conn = get_connection()
        cur = conn.cursor()

        cur.execute("SELECT name FROM users WHERE id=%s", (session["user_id"],))
        user = cur.fetchone()

        if user:
            user_name = user[0]

        cur.close()
        conn.close()

    except Exception as e:
        print("User name fetch error:", e)

   return render_template(
    "index.html",
    user_name=user_name,
    user_id=session["user_id"]
)

# ------------------------
# SIGNUP API
# ------------------------

@app.route("/signup", methods=["POST"])
def signup():

    data = request.json

    name = data.get("name")
    email = data.get("email")
    phone = data.get("phone")
    password = data.get("password")

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT id FROM users WHERE email=%s", (email,))
    existing = cur.fetchone()

    if existing:
        cur.close()
        conn.close()
        return jsonify({"status": "fail", "message": "User already exists"})

    hashed_password = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    cur.execute(
        "INSERT INTO users (name,email,phone,password) VALUES (%s,%s,%s,%s)",
        (name, email, phone, hashed_password)
    )

    conn.commit()

    cur.close()
    conn.close()

    return jsonify({"status": "success"})


# ------------------------
# LOGIN API
# ------------------------

@app.route("/login", methods=["POST"])
def login():

    data = request.json

    email = data.get("email")
    mobile = data.get("mobile")
    password = data.get("password")

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "SELECT id,password FROM users WHERE email=%s AND phone=%s",
        (email, mobile)
    )

    user = cur.fetchone()

    cur.close()
    conn.close()

    if not user:
        return jsonify({"status": "fail", "message": "Invalid credentials"})

    user_id = user[0]
    stored_password = user[1].encode()

    if bcrypt.checkpw(password.encode(), stored_password):

        session["user_id"] = user_id
        return jsonify({"status": "success"})

    else:
        return jsonify({"status": "fail", "message": "Invalid password"})






# ------------------------
# GOOGLE LOGIN
# ------------------------

@app.route("/google-login", methods=["POST"])
def google_login():

    data = request.json
    token = data.get("token")

    try:
        # Decode Google JWT token
        decoded = jwt.decode(token, options={"verify_signature": False})

        email = decoded.get("email")
        name = decoded.get("name", "Google User")

        if not email:
            return jsonify({"status": "fail"})

        conn = get_connection()
        cur = conn.cursor()

        cur.execute("SELECT id FROM users WHERE email=%s", (email,))
        user = cur.fetchone()

        if user:
            user_id = user[0]
        else:
            cur.execute(
                "INSERT INTO users (name,email,phone,password) VALUES (%s,%s,%s,%s)",
                (name, email, "", "")
            )
            conn.commit()

            cur.execute("SELECT id FROM users WHERE email=%s", (email,))
            user_id = cur.fetchone()[0]

        session["user_id"] = user_id

        cur.close()
        conn.close()

        return jsonify({"status": "success"})

    except Exception as e:
        print("Google Login Error:", e)
        return jsonify({"status": "fail"})


# ------------------------
# GENERATE TEXT
# ------------------------

@app.route("/generate", methods=["POST"])
def generate():

    data = request.json
    text = data.get("text")

    prompt = f"Rewrite this text clearly:\n{text}"

    result = call_ai(prompt)

    # SAVE HISTORY
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO history (user_id, action, input_text, output_text)
        VALUES (%s,%s,%s,%s)
        """,
        (session["user_id"], "generate", text, result)
    )

    conn.commit()
    cur.close()
    conn.close()

    return jsonify({"result": result})


# ------------------------
# CORRECT TEXT
# ------------------------

@app.route("/correct", methods=["POST"])
def correct():

    data = request.json
    text = data.get("text")

    prompt = f"Correct grammar of this text:\n{text}"

    result = call_ai(prompt)

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO history (user_id, action, input_text, output_text)
        VALUES (%s,%s,%s,%s)
        """,
        (session["user_id"], "correct", text, result)
    )

    conn.commit()
    cur.close()
    conn.close()

    return jsonify({"result": result})


# ------------------------
# ENHANCE TEXT
# ------------------------

@app.route("/enhance", methods=["POST"])
def enhance():

    data = request.json
    text = data.get("text")

    prompt = f"Improve and enhance this writing:\n{text}"

    result = call_ai(prompt)

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO history (user_id, action, input_text, output_text)
        VALUES (%s,%s,%s,%s)
        """,
        (session["user_id"], "enhance", text, result)
    )

    conn.commit()
    cur.close()
    conn.close()

    return jsonify({"result": result})

# ------------------------
# REGENERATE WITH FEEDBACK
# ------------------------

@app.route("/regenerate", methods=["POST"])
def regenerate():

    data = request.json

    original = data.get("original")
    feedback = data.get("feedback")

    prompt = f"""
    Here is the AI generated text:

    {original}

    The user wants the following changes:
    {feedback}

    Rewrite the text according to the user's feedback.
    """

    result = call_ai(prompt)

    return jsonify({"result": result})

# ------------------------
# TOPIC GENERATOR
# ------------------------

@app.route("/topic", methods=["POST"])
def topic():

    data = request.json

    topic = data.get("topic")
    length = data.get("length")

    prompt = f"Write a {length} description about {topic}"

    result = call_ai(prompt)

    return jsonify({"result": result})


# ------------------------
# LOGOUT
# ------------------------

@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("login_page"))
    # ------------------------
# WORD COUNT
# ------------------------

@app.route("/wordcount", methods=["POST"])
def wordcount():

    data = request.json
    text = data.get("text","")

    words = len(text.split())
    chars = len(text)

    return jsonify({
        "words": words,
        "characters": chars
    })


# ------------------------
# PROFESSIONALISM CHECK
# ------------------------

@app.route("/professional", methods=["POST"])
def professional():

    data = request.json
    text = data.get("text")

    prompt = f"""
    Analyze the professionalism of the following text.
    Give a professionalism score out of 10 and explain briefly.

    Text:
    {text}
    """

    result = call_ai(prompt)

    return jsonify({"result": result})


# ------------------------
# PLAGIARISM CHECK (AI ESTIMATE)
# ------------------------

@app.route("/plagiarism", methods=["POST"])
def plagiarism():

    data = request.json
    text = data.get("text")

    prompt = f"""
    Estimate plagiarism risk for this text.
    Give percentage originality and explain briefly.

    Text:
    {text}
    """

    result = call_ai(prompt)

    return jsonify({"result": result})


# ------------------------

if __name__ == "__main__":
    app.run(debug=True)
