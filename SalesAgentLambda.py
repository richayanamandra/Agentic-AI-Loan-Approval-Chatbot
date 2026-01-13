import json
import os
import requests

# ================= CONFIG =================
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant")

# ================= LLM HELPER =================
def generate_sales_response(base_text):
    """
    LLM is used ONLY to improve tone and clarity.
    It must NEVER introduce new steps or questions.
    """
    if not GROQ_API_KEY:
        return base_text

    system_prompt = """
You are a senior Tata Capital sales advisor.

Your task:
- Rewrite the given message to sound confident, warm, and reassuring
- Keep it concise and professional

STRICT RULES:
- Do NOT add questions
- Do NOT add new steps
- Do NOT change the meaning
- Do NOT mention KYC, underwriting, or approval
"""

    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": base_text}
        ],
        "temperature": 0.3,
        "max_tokens": 180
    }

    r = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        },
        json=payload,
        timeout=8
    )

    return r.json()["choices"][0]["message"]["content"]

# ================= MAIN HANDLER =================
def lambda_handler(event, context):
    """
    Expected input:
    {
        "action": "PRESENT_OFFER" | "EXPLAIN_EMI" | "REASSURE",
        "loan_type": "EDUCATION",
        "amount": 1200000,
        "tenure": 60,
        "emi": 27000,
        "sentiment": "HESITANT" | "NEUTRAL"
    }
    """

    action = event.get("action")
    loan_type = event.get("loan_type", "").lower()
    amount = event.get("amount")
    tenure = event.get("tenure")
    emi = event.get("emi")
    sentiment = event.get("sentiment", "NEUTRAL")

    # ---------- BASE MESSAGE (DETERMINISTIC) ----------
    if action == "PRESENT_OFFER":
        if sentiment == "HESITANT":
            base_text = (
                f"I understand this can feel like a big decision, especially if this is your first loan. "
                f"For your {loan_type} loan of ₹{amount:,} over {tenure//12} years, "
                f"your estimated EMI would be around ₹{emi:,} per month. "
                "We can always adjust the amount or tenure to make this comfortable for you."
            )
        else:
            base_text = (
                f"For your {loan_type} loan of ₹{amount:,} over {tenure//12} years, "
                f"your estimated EMI would be around ₹{emi:,} per month."
            )

    elif action == "EXPLAIN_EMI":
        base_text = (
            f"An EMI is simply the fixed amount you repay every month. "
            f"In your case, ₹{emi:,} would be paid monthly for {tenure//12} years, "
            "which helps spread the cost evenly without sudden financial pressure."
        )

    elif action == "REASSURE":
        base_text = (
            "It’s completely normal to have doubts before taking a loan. "
            "There’s absolutely no pressure to move forward until you feel confident. "
            "I’m here to help you understand every detail before you decide."
        )

    else:
        base_text = "Let’s take this step by step."

    # ---------- LLM STYLING ----------
    final_text = generate_sales_response(base_text)

    return {
        "statusCode": 200,
        "body": json.dumps({
            "reply": final_text
        })
    }
