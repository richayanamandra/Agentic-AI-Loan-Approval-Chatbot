import json
import os
import re
import requests
import boto3

# ================= CONFIG =================
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant")

KYC_LAMBDA_NAME = "KYCVerificationLambda"
UNDERWRITING_LAMBDA_NAME = "UnderwritingLambda"

SANCTION_LETTER_URL = (
    "http://sanction-letters-bucket.s3-website-us-east-1.amazonaws.com"
)

lambda_client = boto3.client("lambda")
SESSION_STATE = {}

# ================= EXTRACTION HELPERS =================
def extract_amount(text):
    t = text.lower().replace(",", "")
    if "lakh" in t:
        m = re.search(r"(\d+)", t)
        return int(m.group(1)) * 100000 if m else None

    m = re.search(r"(\d{6,9})", t)
    return int(m.group(1)) if m else None


def extract_tenure(text):
    m = re.search(r"(\d+)\s*(year|years)", text.lower())
    return int(m.group(1)) * 12 if m else None


def extract_loan_type(text):
    for k in ["education", "personal", "home", "auto", "car", "business"]:
        if k in text.lower():
            return k.upper()
    return None


def calculate_emi(p, r, n):
    r = r / (12 * 100)
    return int((p * r * (1 + r) ** n) / ((1 + r) ** n - 1))


# ================= SENTIMENT =================
def detect_sentiment(text):
    t = text.lower()
    if any(
        x in t
        for x in [
            "not sure",
            "unsure",
            "idk",
            "confused",
            "worried",
            "scared",
            "first loan",
            "can i afford",
            "should i take",
        ]
    ):
        return "HESITANT"
    return "NEUTRAL"


def user_accepts_suggestion(text):
    return text.lower() in [
        "okay",
        "ok",
        "fine",
        "sounds good",
        "that works",
        "alright",
    ]


def user_ready(text):
    return text.lower() in [
        "yes",
        "ok",
        "okay",
        "ready",
        "proceed",
        "continue",
    ]


def is_verified(text):
    return "verified" in text.lower()


# ================= LLM (LANGUAGE ONLY) =================
def llm_say(text):
    if not GROQ_API_KEY:
        return text

    system_prompt = """
You are a Tata Capital loan advisor.
You will receive a SYSTEM-GENERATED message.
Your job is ONLY to rephrase it slightly to sound warm, calm, and professional.

ABSOLUTE RULES:
- NEVER speak as the user
- NEVER invent intent
- NEVER add questions
- NEVER introduce new topics
"""

    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
        ],
        "temperature": 0.2,
        "max_tokens": 140,
    }

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


# ================= RESPONSE =================
def respond(text, sid):
    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(
            {
                "reply": text,
                "sessionId": sid,
            }
        ),
    }


# ================= MAIN ORCHESTRATOR =================
def lambda_handler(event, context):
    body = json.loads(event.get("body", "{}"))
    msg = body.get("message", "")
    sid = body.get("sessionId", "demo-user")

    sentiment = detect_sentiment(msg)

    state = SESSION_STATE.get(
        sid,
        {
            "stage": "WELCOME",
            "loan_type": None,
            "amount": None,
            "tenure": None,
            "emi": None,
        },
    )

    # ---------- WELCOME ----------
    if state["stage"] == "WELCOME":
        state["stage"] = "DISCOVERY"
        SESSION_STATE[sid] = state
        return respond(
            llm_say(
                "Hi! Thanks for reaching out. I’m here to help you with your loan and we can take this step by step. "
                "To get started, what kind of loan are you looking for?"
            ),
            sid,
        )

    # ---------- EXTRACTION ----------
    state["loan_type"] = state["loan_type"] or extract_loan_type(msg)
    state["amount"] = state["amount"] or extract_amount(msg)
    state["tenure"] = state["tenure"] or extract_tenure(msg)
    SESSION_STATE[sid] = state

    # ---------- DISCOVERY ----------
    if state["stage"] == "DISCOVERY":

        # ===== HESITATION BLOCK (NEW, SAFE) =====
        if sentiment == "HESITANT":

            if not state["amount"]:
                return respond(
                    llm_say(
                        "That’s completely okay — you don’t have to decide anything right now. "
                        "Even a rough estimate helps me show you what the monthly EMI could look like, "
                        "so you can see whether it feels manageable. We can always change it later."
                    ),
                    sid,
                )

            if not state["tenure"]:
                if user_accepts_suggestion(msg):
                    state["tenure"] = 60  # 5 years
                    SESSION_STATE[sid] = state
                else:
                    return respond(
                        llm_say(
                            "No worries at all.\n\n"
                            "Most loans are usually repaid over 3 to 5 years for small amounts and "
                            "120 months to 240 months for huge amounts. "
                            "We can start with one option just to understand the EMI, and adjust it once you’re comfortable."
                        ),
                        sid,
                    )
        # ===== END HESITATION BLOCK =====

        if not state["loan_type"]:
            return respond(
                llm_say(
                    "Got it. Just to understand your requirement better, what type of loan are you looking for?"
                ),
                sid,
            )

        if not state["amount"]:
            return respond(
                llm_say(
                    "Thanks. Roughly how much loan amount are you considering? An approximate number is perfectly fine."
                ),
                sid,
            )

        if not state["tenure"]:
            return respond(
                llm_say(
                    "That helps. Over how many years would you be comfortable repaying this loan?"
                ),
                sid,
            )

        state["stage"] = "SALES"
        SESSION_STATE[sid] = state

    # ---------- SALES ----------
    if state["stage"] == "SALES":
        state["emi"] = calculate_emi(state["amount"], 13, state["tenure"])
        state["stage"] = "CONFIRM"
        SESSION_STATE[sid] = state

        if sentiment == "HESITANT":
            text = (
                f"I completely understand — this can feel like a big decision. "
                f"Based on what you’ve shared, for a loan of ₹{state['amount']:,} over {state['tenure']//12} years, "
                f"the estimated EMI would be around ₹{state['emi']:,} per month. "
                "We can adjust things if needed."
            )
        else:
            text = (
                f"Thanks for sharing those details. Based on what you’ve told me, "
                f"for a loan of ₹{state['amount']:,} over {state['tenure']//12} years, "
                f"your estimated EMI would be around ₹{state['emi']:,} per month."
            )

        return respond(llm_say(text), sid)

    # ---------- CONFIRM ----------
    if state["stage"] == "CONFIRM":
        if user_ready(msg):
            state["stage"] = "KYC"
            SESSION_STATE[sid] = state
            return respond(
                llm_say(
                    "Great, thanks for confirming. The next step is KYC verification. "
                    "Once you’ve completed it, just type 'verified' here and I’ll take it forward."
                ),
                sid,
            )

        return respond(
            llm_say(
                "No rush at all. Take your time, and just let me know when you’re comfortable moving ahead."
            ),
            sid,
        )

    # ---------- KYC ----------
    if state["stage"] == "KYC":
        if not is_verified(msg):
            return respond(
                llm_say(
                    "Whenever your KYC is completed, just type 'verified' here. I’ll handle the rest for you."
                ),
                sid,
            )

        kyc_resp = lambda_client.invoke(
            FunctionName=KYC_LAMBDA_NAME,
            InvocationType="RequestResponse",
            Payload=json.dumps(state),
        )

        kyc_data = json.loads(json.loads(kyc_resp["Payload"].read())["body"])

        if kyc_data.get("kyc_status") == "VERIFIED":
            state["stage"] = "UNDERWRITING"
            SESSION_STATE[sid] = state
            return respond(
                llm_say(
                    "Thanks for confirming. I’ve checked your KYC, and everything looks good. "
                    "Let’s quickly move ahead and check your loan eligibility."
                ),
                sid,
            )

        return respond(
            llm_say("I couldn’t verify your KYC right now. Please try again shortly."),
            sid,
        )

    # ---------- UNDERWRITING ----------
    if state["stage"] == "UNDERWRITING":
        uw_resp = lambda_client.invoke(
            FunctionName=UNDERWRITING_LAMBDA_NAME,
            InvocationType="RequestResponse",
            Payload=json.dumps(state),
        )

        uw_data = json.loads(json.loads(uw_resp["Payload"].read())["body"])

        if uw_data.get("decision") == "APPROVED":
            state["stage"] = "SANCTION"
            SESSION_STATE[sid] = state
            return respond(
                llm_say(
                    "Good news! Based on the checks, your loan has been approved. "
                    "I’m sharing your sanction letter with you now."
                ),
                sid,
            )

        return respond(
            llm_say(
                "Based on the current checks, the loan may not be approved right now. "
                "I can help explore alternatives if you’d like."
            ),
            sid,
        )

    # ---------- SANCTION Letter ----------
    if state["stage"] == "SANCTION":
        state["stage"] = "DONE"
        SESSION_STATE[sid] = state
        return respond(
            llm_say(
                "🎉 That’s great news — your loan has been approved.<br><br>"
                "You can view and download your sanction letter here:<br><br>"
                "<a href='http://sanction-letters-bucket.s3-website-us-east-1.amazonaws.com' "
                "target='_blank' style='color:#0a66c2; font-weight:600;'>"
                "📄 Your Sanction Letter</a><br><br>"
                "If you need help with anything after this, I’m right here."
            ),
            sid,
        )

    return respond("I’m here to help.", sid)
