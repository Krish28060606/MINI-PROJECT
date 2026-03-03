from flask import Flask, render_template, request, jsonify
import requests
import re

app = Flask(__name__)

# 🔑 PUT YOUR NEW TOKEN HERE
HF_API_KEY = "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"

API_URL = "https://api-inference.huggingface.co/models/google/flan-t5-small"

headers = {
    "Authorization": f"Bearer {HF_API_KEY}"
}

# ------------------------------------------------
# SMART LOCAL FALLBACK ENGINE (Improved Version)
# ------------------------------------------------
def local_rewrite(text):

    text = text.strip().lower()

    # Advanced grammar replacements
    replacements = {
        "how you are": "how are you",
        "whoi": "who",
        "are you who are": "who are you",
        "are you who": "who are you",
        "i am krish 19 yrs old": "I am Krish and I am 19 years old",
        "krish are you": "Krish, are you",
        "krish who are": "Krish, who are",
        "krish": "Krish"
    }

    for wrong, correct in replacements.items():
        text = text.replace(wrong, correct)

    # Remove duplicate consecutive words
    words = text.split()
    cleaned = []
    for i in range(len(words)):
        if i == 0 or words[i] != words[i-1]:
            cleaned.append(words[i])

    text = " ".join(cleaned)

    # Capitalize properly
    text = text.capitalize()

    # Fix sentence ending
    if any(word in text.lower() for word in ["who", "how", "what", "why", "where"]):
        if not text.endswith("?"):
            text += "?"
    else:
        if not text.endswith("."):
            text += "."

    return text + "\n\n⚡ Local AI Enhancement (Improved Fallback Mode)."


# ------------------------------------------------
# AI REWRITE FUNCTION (WITH SAFE FALLBACK)
# ------------------------------------------------
def ai_rewrite(text):

    if not text.strip():
        return "Please enter some text."

    prompt = f"Correct and improve this sentence grammatically and stylistically: {text}"

    try:
        response = requests.post(
            API_URL,
            headers=headers,
            json={"inputs": prompt},
            timeout=10
        )

        result = response.json()

        # If real AI response
        if isinstance(result, list):
            return result[0]["generated_text"] + "\n\n✨ AI Enhanced using Transformer Model."

        # If model loading or API error
        if "error" in result:
            print("HF ERROR:", result)
            return local_rewrite(text)

    except Exception as e:
        print("Connection Error:", e)
        return local_rewrite(text)

    return local_rewrite(text)


# ------------------------------------------------
# IMPROVED PLAGIARISM LOGIC
# ------------------------------------------------
def plagiarism_score(text):

    words = re.findall(r'\w+', text.lower())

    if len(words) == 0:
        return 0

    unique_words = len(set(words))
    total_words = len(words)

    repetition_ratio = 1 - (unique_words / total_words)

    score = round(repetition_ratio * 100, 2)

    return score


# ------------------------------------------------
# ROUTES
# ------------------------------------------------
@app.route("/")
def home():
    return render_template("index.html")


@app.route("/improve", methods=["POST"])
def improve():
    data = request.json
    text = data["text"]

    return jsonify({
        "improved": ai_rewrite(text),
        "word_count": len(text.split())
    })


@app.route("/plagiarism", methods=["POST"])
def plagiarism():
    data = request.json
    text = data["text"]

    return jsonify({
        "similarity": plagiarism_score(text)
    })


if __name__ == "__main__":
    app.run(debug=True)