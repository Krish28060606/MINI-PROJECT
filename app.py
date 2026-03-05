from flask import Flask, render_template, request, jsonify
import requests
import re
import bcrypt
import base64
import json
from db import get_connection

app = Flask(__name__)

# ------------------------
# GROQ API
# ------------------------

GROQ_API_KEY = "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"

API_URL = "https://api.groq.com/openai/v1/chat/completions"

headers = {
    "Authorization": f"Bearer {GROQ_API_KEY}",
    "Content-Type": "application/json"
}

# ------------------------
# Protect Proper Names
# ------------------------

def protect_names(text):

    names = re.findall(r'\b[A-Z][a-z]+\s[A-Z][a-z]+\b', text)

    protected = {}

    for i, name in enumerate(names):
        placeholder = f"NAME{i}"
        protected[placeholder] = name
        text = text.replace(name, placeholder)

    return text, protected


def restore_names(text, protected):

    for placeholder, name in protected.items():
        text = text.replace(placeholder, name)

    return text


# ------------------------
# Call AI
# ------------------------

def call_ai(prompt):

    payload = {
        "model": "openai/gpt-oss-120b",
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.5
    }

    response = requests.post(API_URL, headers=headers, json=payload)

    if response.status_code != 200:
        return "AI Error"

    result = response.json()

    return result["choices"][0]["message"]["content"]


# ------------------------
# ROUTES
# ------------------------

@app.route("/")
def login_page():
    return render_template("login.html")


@app.route("/index")
def index():
    return render_template("index.html")


# ------------------------
# SIGNUP
# ------------------------

@app.route("/signup", methods=["POST"])
def signup():

    data = request.json

    name = data.get("name")
    email = data.get("email")
    phone = data.get("phone")
    password = data.get("password")

    hashed_password = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "INSERT INTO users (name,email,phone,password) VALUES (%s,%s,%s,%s)",
        (name, email, phone, hashed_password)
    )

    conn.commit()

    cur.close()
    conn.close()

    return jsonify({"message": "User created"})


# ------------------------
# LOGIN
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
        return jsonify({"status": "fail"})

    user_id = user[0]
    stored_password = user[1].encode()

    if bcrypt.checkpw(password.encode(), stored_password):
        return jsonify({
            "status": "success",
            "user_id": user_id
        })
    else:
        return jsonify({"status": "fail"})


# ------------------------
# AI IMPROVE
# ------------------------

@app.route("/improve", methods=["POST"])
def improve():

    data = request.json
    text = data.get("text", "")
    user_id = data.get("user_id", 1)

    protected_text, protected_names = protect_names(text)

    corrected_prompt = f"Correct grammar only.\n\n{protected_text}"
    enhanced_prompt = f"Rewrite professionally.\n\n{protected_text}"

    corrected = call_ai(corrected_prompt)
    enhanced = call_ai(enhanced_prompt)

    corrected = restore_names(corrected, protected_names)
    enhanced = restore_names(enhanced, protected_names)

    # ------------------------
    # SAVE HISTORY
    # ------------------------

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO ai_history (user_id,input_text,corrected_text,enhanced_text)
        VALUES (%s,%s,%s,%s)
    """,(user_id,text,corrected,enhanced))

    conn.commit()

    cur.close()
    conn.close()

    return jsonify({
        "corrected": corrected,
        "enhanced": enhanced
    })


# ------------------------
# PLAGIARISM
# ------------------------

@app.route("/plagiarism", methods=["POST"])
def plagiarism():

    data = request.json
    text = data.get("text", "")

    words = text.split()

    unique_words = len(set(words))
    total_words = len(words)

    if total_words == 0:
        similarity = 0
    else:
        similarity = int((1 - unique_words / total_words) * 100)

    return jsonify({"similarity": similarity})


# ------------------------
# LOGOUT
# ------------------------

@app.route("/logout")
def logout():
    return jsonify({"status": "logged_out"})


# ------------------------
# GOOGLE LOGIN
# ------------------------

@app.route("/google-login", methods=["POST"])
def google_login():

    data = request.json
    token = data.get("token")

    payload = token.split('.')[1]
    payload += '=' * (-len(payload) % 4)

    decoded = json.loads(base64.b64decode(payload))

    email = decoded["email"]
    name = decoded.get("name","Google User")

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT id FROM users WHERE email=%s",(email,))
    user = cur.fetchone()

    if not user:

        cur.execute(
            "INSERT INTO users (name,email,phone,password) VALUES (%s,%s,%s,%s)",
            (name,email,"google_user","google_auth")
        )

        conn.commit()

    cur.close()
    conn.close()

    return jsonify({"status":"success"})


# ------------------------

if __name__ == "__main__":
    app.run(debug=True)
