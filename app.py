from time import time

REQUEST_LOG = {}
MAX_REQUESTS_PER_IP_PER_HOUR = 5
WINDOW_SECONDS = 60 * 60  # 1 hour

import os
from flask import Flask, request, jsonify, send_from_directory
from dotenv import load_dotenv
from groq import Groq

load_dotenv()
app = Flask(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")  # ← Keep this EXACTLY like this

client = Groq(api_key=GROQ_API_KEY)

@app.route("/")
def index():
    return send_from_directory(".", "index.html")

@app.route("/api/plan", methods=["POST"])
def api_plan():
    data = request.get_json() or {}
    goals = (data.get("goals") or "").strip()
    text = goals.lower()

    # Very simple red-flag detection (you can expand this over time)
    RED_FLAGS = [
        "kill myself", "end my life", "suicide", "self-harm", "self harm",
        "hurt myself", "hurt other people", "kill someone", "murder",
        "shooting", "bomb", "explosive",
        "diagnose me", "what medication should i take",
        "legal advice", "should i plead", "defend me in court"
    ]

    if any(phrase in text for phrase in RED_FLAGS):
        return jsonify({
            "error": "SAFETY_BLOCKED"
        }), 400
    
    # Simple rate limit by IP
    ip = request.remote_addr or "unknown"
    now = time()

    timestamps = REQUEST_LOG.get(ip, [])
    timestamps = [t for t in timestamps if now - t < WINDOW_SECONDS]

    if len(timestamps) >= MAX_REQUESTS_PER_IP_PER_HOUR:
        return jsonify({
            "error": "RATE_LIMIT_IP"
        }), 429

    timestamps.append(now)
    REQUEST_LOG[ip] = timestamps

    if not goals:
        return jsonify({"error": "No goals provided."}), 400

    quote_prompt = f"""
You are a focused, gentle planning companion named CHYF (Chidinma Helps You Focus).
Given the user's goals for today:
"{goals}"

Produce ONLY:
QUOTE: "a short, original, motivating quote tailored to these goals"
AUTHOR: "Chidinma Helps You Focus"
""".strip()

    plan_prompt = f"""
You are CHYF (Chidinma Helps You Focus), a calm but practical planning companion.

User's message:
"{goals}"

Your job is to quietly understand what they want and then give them a clear, simple, ordered plan. Do NOT explain what you are doing. Do NOT talk about what is or is not "needed". Do NOT add extra commentary. Just give the plan as a list.

First, silently decide which ONE of these this looks most like:
- TYPE A: mainly a full or partial day/evening plan (tasks, work, life, maybe including a focused session like gym or cooking)
- TYPE B: mainly a single focused session request (e.g., "I'm going to the gym, help me out", "Help me cook X", "Help me write Y")

If TYPE B (single focused session):
- Do NOT invent a full-day schedule.
- Create ONLY a clear, doable plan for that session.
- Organize it into a few ordered steps or phases (for example: prepare / main work / finish, or warm-up / main sets / cool-down).
- If it's a workout, you may label the whole list "GYM PLAN:" on the first line.
- If it's something else (cooking, writing, etc.), you may label the whole list appropriately on the first line (e.g., "COOKING PLAN:", "WRITING PLAN:").
- Do NOT create any extra named plan sections beyond that one.

If TYPE A (day/evening/tasks plan):
- Give a realistic day or evening with 3–6 ordered steps.
- Respect time clues:
  - If they say "tonight", focus on evening.
  - If they say "after work" or mention work hours, start after that.
  - If they do not mention work at all, do NOT invent a detailed work block.
- Group similar tasks together when it helps focus.
- Include short breaks and transitions only when useful.
- If there is a specific focused session inside the day (like gym or cooking), you may include that within one of the steps, but do NOT create a separate named "PLAN" section for it.

In ALL cases, respond in EXACTLY this structure (no extra lines before or after, no duplicated sections):

PLAN:
1. ...
2. ...
3. ...
4. ...
(You may add 5. and 6. if genuinely helpful, but no more.)

Never output headers like "GYM PLAN:" as a second section. If you need a label like that, fold it into the text of one of the numbered steps (for example: "3. GYM PLAN: ...").
""".strip()



    try:
        # Call Groq for quote
        quote_resp = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": quote_prompt}],
            max_tokens=200,
            temperature=0.7,
        )
        quote_text = quote_resp.choices[0].message.content

        # Call Groq for plan
        plan_resp = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": plan_prompt}],
            max_tokens=600,
            temperature=0.7,
        )
        plan_text = plan_resp.choices[0].message.content

        return jsonify({
            "quote": quote_text,
            "plan": plan_text
        })

    except Exception as e:
        import groq
        print("CHYF backend error:", repr(e))
        return jsonify({"error": "GENERIC_ERROR"}), 500

if __name__ == "__main__":
    app.run(debug=True, port=8000)

