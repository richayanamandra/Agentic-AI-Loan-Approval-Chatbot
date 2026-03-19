"""
SalesAgentLambda.py

Worker Agent: Sales / Offer Presentation
- Takes customer profile + loan ask
- Generates a personalized, persuasive loan offer
- Uses Groq LLaMA for natural language, deterministic logic for numbers
- Never invents numbers or changes business rules

Input:
{
    "action": "PRESENT_OFFER" | "EXPLAIN_EMI" | "REASSURE" | "UPSELL" | "COUNTER_OFFER",
    "customer": { ...KYC profile... },
    "loan_amount": 1200000,
    "tenure_months": 60,
    "emi": 27000,
    "interest_rate": 13.5,
    "sentiment": "HESITANT" | "NEUTRAL",
    "counter_amount": 800000   # optional, for COUNTER_OFFER
}
"""

import json
import os
import math
import requests

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant")


def calculate_emi(principal, annual_rate, months):
    r = annual_rate / (12 * 100)
    if r == 0:
        return principal / months
    return math.ceil((principal * r * (1 + r) ** months) / ((1 + r) ** months - 1))


def llm_style(base_text, system_prompt):
    """Call Groq to improve tone/phrasing. Falls back to base_text on failure."""
    if not GROQ_API_KEY:
        return base_text

    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": base_text},
        ],
        "temperature": 0.25,
        "max_tokens": 200,
    }

    try:
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=8,
        )
        return r.json()["choices"][0]["message"]["content"]
    except Exception:
        return base_text


SALES_SYSTEM_PROMPT = """
You are a warm, professional senior loan advisor at Loanify.

Your ONLY job: Rephrase the given message to sound empathetic, confident and human.

ABSOLUTE RULES:
- Never change any numbers (EMI, loan amount, interest rate, tenure)
- Never add steps, questions, or topics not in the original message
- Never mention KYC, underwriting, approval process, or next steps
- Keep it concise — 2-4 sentences max
- Sound like a helpful human advisor, not a bot
"""


def lambda_handler(event, context):
    action = event.get("action", "PRESENT_OFFER")
    customer = event.get("customer", {})
    loan_amount = int(event.get("loan_amount", 0))
    tenure_months = int(event.get("tenure_months", 60))
    emi = int(event.get("emi", 0))
    interest_rate = float(event.get("interest_rate", 13.5))
    sentiment = event.get("sentiment", "NEUTRAL")
    counter_amount = event.get("counter_amount")

    customer_name = customer.get("name", "").split()[0] if customer.get("name") else ""
    city = customer.get("city", "")
    monthly_salary = int(customer.get("monthly_salary", 0)) if customer.get("monthly_salary") else 0
    pre_approved_limit = int(customer.get("pre_approved_limit", 0)) if customer.get("pre_approved_limit") else 0

    # EMI as % of salary — useful for reassurance
    emi_pct = round((emi / monthly_salary) * 100) if monthly_salary > 0 else 0

    # ── Build deterministic base message ────────────────────────────────────
    if action == "PRESENT_OFFER":
        if sentiment == "HESITANT":
            base_text = (
                f"I understand this can feel like a big decision{', ' + customer_name if customer_name else ''}. "
                f"Let me walk you through it simply: for a personal loan of ₹{loan_amount:,} over {tenure_months // 12} years "
                f"at {interest_rate}% interest, your monthly EMI would be ₹{emi:,}. "
            )
            if monthly_salary > 0:
                base_text += (
                    f"That's only {emi_pct}% of your monthly income — well within a comfortable range. "
                    "We can also adjust the tenure to reduce the EMI if needed."
                )
        else:
            base_text = (
                f"Great news{', ' + customer_name if customer_name else ''}! "
                f"For a personal loan of ₹{loan_amount:,} over {tenure_months // 12} years "
                f"at {interest_rate}% p.a., your EMI comes to ₹{emi:,} per month."
            )
            if pre_approved_limit > 0 and loan_amount <= pre_approved_limit:
                base_text += " Since you're within your pre-approved limit, this can be processed quickly."

    elif action == "EXPLAIN_EMI":
        base_text = (
            f"An EMI (Equated Monthly Instalment) is simply the fixed amount you repay every month. "
            f"For your loan, ₹{emi:,} per month for {tenure_months} months covers both the principal "
            f"and the interest at {interest_rate}% per annum. "
            f"At the end of {tenure_months // 12} years, the loan is fully repaid."
        )
        if monthly_salary > 0:
            base_text += f" This is {emi_pct}% of your salary, leaving you plenty for other expenses."

    elif action == "REASSURE":
        base_text = (
            "It's completely natural to pause and think before taking a loan — and that's actually a great sign. "
            "Tata Capital has helped over 4 million customers across India with flexible, transparent loans. "
            "There's no obligation or pressure — I'm here to help you understand your options fully before you decide."
        )

    elif action == "COUNTER_OFFER":
        counter_emi = calculate_emi(counter_amount, interest_rate, tenure_months) if counter_amount else 0
        base_text = (
            f"I understand. Based on your situation, we can offer a revised loan of ₹{counter_amount:,} "
            f"over {tenure_months // 12} years, which brings your EMI down to ₹{counter_emi:,} per month. "
            "This might be a more comfortable starting point."
        )

    elif action == "UPSELL":
        # Customer's pre-approved limit > what they asked for
        base_text = (
            f"You're actually eligible for up to ₹{pre_approved_limit:,} based on your profile. "
            f"If you'd like, we can explore a higher amount — even a small increase could give you more flexibility "
            "for expenses like home renovation, travel, or consolidating other loans."
        )
    else:
        base_text = "Let me know how I can help you further with your loan requirements."

    final_text = llm_style(base_text, SALES_SYSTEM_PROMPT)

    return {
        "statusCode": 200,
        "body": json.dumps({
            "reply": final_text,
            "emi": emi,
            "interest_rate": interest_rate,
        }),
    }
