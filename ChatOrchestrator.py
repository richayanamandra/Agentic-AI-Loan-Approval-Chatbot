import json, os, re, uuid, math, boto3, requests, time
from datetime import datetime, timedelta

# ── Key rotation ──────────────────────────────────────────────────────────────
_GROQ_KEYS = [k for k in [
    os.environ.get("GROQ_API_KEY_1"),
    os.environ.get("GROQ_API_KEY_2"),
    os.environ.get("GROQ_API_KEY_3"),
    os.environ.get("GROQ_API_KEY_4"),
    os.environ.get("GROQ_API_KEY"),  # fallback to single key if set
] if k]

GROQ_MODEL      = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
KYC_LAMBDA      = os.environ.get("KYC_LAMBDA_NAME", "KYCVerificationLambda")
UW_LAMBDA       = os.environ.get("UNDERWRITING_LAMBDA_NAME", "UnderwritingLambda")
SANCTION_LAMBDA = os.environ.get("SANCTION_LAMBDA_NAME", "SanctionLetterLambda")
SESSION_TABLE   = os.environ.get("SESSION_TABLE", "loan_sessions")
MAX_ROUNDS      = 4

lambda_client = boto3.client("lambda")
dynamodb      = boto3.resource("dynamodb")
sessions      = dynamodb.Table(SESSION_TABLE)

# ── Session ───────────────────────────────────────────────────────────────────
def get_session(sid):
    try:
        r = sessions.get_item(Key={"session_id": sid})
        item = r.get("Item")
        if item:
            return json.loads(item["data"])
    except Exception as e:
        print(f"Session read error: {e}")
    return {
        "history": [],
        "customer": None,
        "loan_amount": None,
        "tenure_months": None,
        "salary_slip_uploaded": False,
        "underwriting_result": None,
        "sanction_details": None,
        "phone": None,
        "kyc_confirmed": False,
        "pdf_url": None,
    }

def save_session(sid, state):
    try:
        sessions.put_item(Item={
            "session_id": sid,
            "data": json.dumps(state),
            "ttl": int(datetime.now().timestamp()) + 86400 * 7,
        })
    except Exception as e:
        print(f"Session save error: {e}")

# ── Helpers ───────────────────────────────────────────────────────────────────
def _get_rate(score):
    if score >= 800: return 11.5
    if score >= 750: return 12.5
    return 13.5

def _calc_emi(p, r, n):
    if not p or not n: return 0
    r = r / (12 * 100)
    if r == 0: return int(p / n)
    return int((p * r * (1 + r) ** n) / ((1 + r) ** n - 1)) + 1

# ── Tools ─────────────────────────────────────────────────────────────────────
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "verify_kyc",
            "description": (
                "Look up the customer's details from our CRM database using their phone number. "
                "Call this as soon as the customer shares their mobile number — do not wait. "
                "Returns their full name, address, PAN, employer, credit score, pre-approved loan limit, and monthly salary. "
                "After getting the result, display ALL the details to the customer and ask them to confirm everything is correct."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "phone": {"type": "string", "description": "Customer's 10-digit mobile number"}
                },
                "required": ["phone"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_underwriting",
            "description": (
                "Run the credit eligibility and underwriting check. "
                "Call this ONLY after: (1) KYC is verified, (2) customer has confirmed their KYC details are correct, "
                "and (3) customer has explicitly agreed to proceed with the loan. "
                "Returns APPROVED, REJECTED, or PENDING_SALARY_SLIP."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "loan_amount":   {"type": "integer", "description": "Loan amount in rupees"},
                    "tenure_months": {"type": "integer", "description": "Loan tenure in months"}
                },
                "required": ["loan_amount", "tenure_months"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_sanction_letter",
            "description": (
                "Generate the official PDF sanction letter and return a secure download URL. "
                "Call this IMMEDIATELY after underwriting returns APPROVED — do not wait for the customer to ask. "
                "Returns a pdf_url which you must share with the customer as a download link."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_underwriting_with_salary_slip",
            "description": (
                "Re-run underwriting after the customer has uploaded their salary slip. "
                "Call this when underwriting previously returned PENDING_SALARY_SLIP "
                "and the customer confirms they have uploaded their salary slip."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "loan_amount":   {"type": "integer", "description": "Loan amount in rupees"},
                    "tenure_months": {"type": "integer", "description": "Loan tenure in months"}
                },
                "required": ["loan_amount", "tenure_months"]
            }
        }
    },
]

# ── Tool execution ────────────────────────────────────────────────────────────
def execute_tool(name, args, state, sid):
    print(f"[TOOL CALLED] {name}({args})")

    if name == "verify_kyc":
        phone = str(args.get("phone", "")).strip().replace(" ", "").replace("-", "")
        state["phone"] = phone
        try:
            r = lambda_client.invoke(
                FunctionName=KYC_LAMBDA,
                InvocationType="RequestResponse",
                Payload=json.dumps({"phone": phone})
            )
            result = json.loads(json.loads(r["Payload"].read())["body"])
            if result.get("kyc_status") == "VERIFIED":
                state["customer"] = result["customer"]
            print(f"[KYC RESULT] {result}")
            return json.dumps(result)
        except Exception as e:
            return json.dumps({"error": str(e), "kyc_status": "ERROR"})

    elif name in ("run_underwriting", "run_underwriting_with_salary_slip"):
        loan_amount   = int(args.get("loan_amount",   state.get("loan_amount", 0)))
        tenure_months = int(args.get("tenure_months", state.get("tenure_months", 60)))
        state["loan_amount"]   = loan_amount
        state["tenure_months"] = tenure_months
        salary_uploaded = (name == "run_underwriting_with_salary_slip")
        if salary_uploaded:
            state["salary_slip_uploaded"] = True
        try:
            r = lambda_client.invoke(
                FunctionName=UW_LAMBDA,
                InvocationType="RequestResponse",
                Payload=json.dumps({
                    "customer":             state.get("customer", {}),
                    "loan_amount":          loan_amount,
                    "tenure_months":        tenure_months,
                    "salary_slip_uploaded": salary_uploaded,
                })
            )
            result = json.loads(json.loads(r["Payload"].read())["body"])
            state["underwriting_result"] = result.get("decision")
            if result.get("decision") == "APPROVED":
                state["sanction_details"] = result.get("sanction_details")
            print(f"[UW RESULT] {result}")
            return json.dumps(result)
        except Exception as e:
            return json.dumps({"error": str(e)})

    elif name == "generate_sanction_letter":
        sd = state.get("sanction_details")
        c  = state.get("customer", {})
        if not sd:
            rate = _get_rate(c.get("credit_score", 750))
            sd = {
                "sanction_id":       f"LF-{datetime.now().year}-{str(uuid.uuid4())[:6].upper()}",
                "customer_name":     c.get("name", "Valued Customer"),
                "customer_address":  c.get("address", "As per KYC"),
                "customer_pan":      c.get("pan", "As per KYC"),
                "customer_employer": c.get("employer", "As per KYC"),
                "loan_amount":       state.get("loan_amount", 0),
                "interest_rate":     rate,
                "tenure_months":     state.get("tenure_months", 60),
                "emi":               _calc_emi(state.get("loan_amount", 0), rate, state.get("tenure_months", 60)),
                "sanction_date":     datetime.now().strftime("%d %B %Y"),
                "valid_until":       (datetime.now() + timedelta(days=30)).strftime("%d %B %Y"),
            }
            state["sanction_details"] = sd
        try:
            r = lambda_client.invoke(
                FunctionName=SANCTION_LAMBDA,
                InvocationType="RequestResponse",
                Payload=json.dumps({"sanction_details": sd, "session_id": sid})
            )
            result = json.loads(json.loads(r["Payload"].read())["body"])
            # ── Store PDF URL in session so it is never lost or truncated ──
            if result.get("pdf_url"):
                state["pdf_url"] = result["pdf_url"]
            print(f"[SANCTION RESULT] {result}")
            return json.dumps(result)
        except Exception as e:
            return json.dumps({"error": str(e)})

    return json.dumps({"error": f"Unknown tool: {name}"})

# ── System prompt ─────────────────────────────────────────────────────────────
def build_system_prompt(state):
    customer  = state.get("customer")
    uw_result = state.get("underwriting_result")

    prompt = """You are Tia, a senior loan advisor at Loanify. You are warm, human, empathetic, and genuinely helpful.
You are having a real-time chat with a customer. You have tools to verify their identity, check loan eligibility, and generate their sanction letter.

YOUR PERSONALITY:
- Speak like a knowledgeable friend who works in finance — never robotic, never scripted
- Use natural Indian English: "That's great!", "Don't worry at all", "Let me sort this out for you"
- Be empathetic FIRST, transactional SECOND — always address emotions before asking for data
- Use contractions naturally: "I'll", "you'll", "let's", "don't", "I've", "it's"
- Vary your sentence starters — never begin two consecutive messages the same way
- When someone shares good news or agrees, sound genuinely excited
- When delivering bad news, be warm and solution-focused, never clinical

YOUR LOAN KNOWLEDGE (use naturally, don't recite like a brochure):
LOAN PRODUCTS:
- Personal/Student/Education loans: 11.5-13.5% p.a. No collateral needed. Instant digital process.
- Home loans, Car loans, Business loans also available

EMI:
- EMI = fixed monthly payment covering principal + interest
- Formula: P x r x (1+r)^n / ((1+r)^n - 1) where r = annual_rate / (12 x 100)
- Longer tenure = lower EMI but more total interest paid
- Shorter tenure = higher EMI but you save on total interest
- Total amount payable = EMI x tenure months
- Total interest = (EMI x tenure months) minus principal

CREDIT SCORE TO INTEREST RATE:
- 800 or above: 11.5% per annum (best rate)
- 750 to 799: 12.5% per annum
- 700 to 749: 13.5% per annum
- Below 700: likely ineligible, but explore options

STUDENT / EDUCATION LOAN:
- Designed exactly for students — investing in your future, not a burden
- Repayment typically starts 6-12 months after course completion (moratorium period)
- Parents can be co-applicants which sometimes improves eligibility
- Most students comfortably repay from their first job salary
- Pre-payment allowed after 12 EMIs

HANDLING HESITATION:
- Unsure about amount: ask what it's for, help them size it
- Unsure about tenure: suggest options, show EMI for each
- Worried about repayment: explain moratorium, pre-payment, restructuring
- Worried about burden: "A loan is a financial tool — used wisely, it's an investment"
- First time: normalise it, walk through step by step, be patient
- Always show numbers. People feel better when they can see the math.

THE JOURNEY (follow naturally, never make it feel like a checklist):
STEP 1 - UNDERSTAND AND CONNECT
- Understand loan type, amount, tenure conversationally
- Ask ONE question at a time
- Address hesitation fully before moving on
- Answer any questions about EMI, interest, total payable using your knowledge
- Calculate and share EMI estimate once you have amount and tenure

STEP 2 - COLLECT PHONE NUMBER
- Once comfortable with EMI, ask: "To check your actual pre-approved offer and eligibility, may I have your registered mobile number?"
- Do not ask until they have seen the EMI and seem comfortable

STEP 3 - KYC VERIFICATION
- Call verify_kyc as soon as you get their phone number
- After result, present ALL details clearly:
  "I've verified your details! Here's what I have on file:
  Name: [name]
  Address: [address]
  PAN: [pan]
  Employer: [employer]
  Monthly salary: Rs.[salary]
  Does everything look correct?"
- Wait for confirmation before proceeding

STEP 4 - PRESENT PERSONALISED OFFER
- Use real credit score for interest rate
- Recalculate EMI with correct rate
- Mention pre-approved limit
- Show total payable and total interest
- Ask if they'd like to proceed

STEP 5 - UNDERWRITING
- Call run_underwriting ONLY after customer explicitly agrees
- Say "Give me just a moment while I run your eligibility check..."

STEP 6 - HANDLE RESULT
- APPROVED: immediately call generate_sanction_letter, share pdf_url as download link
- PENDING_SALARY_SLIP: explain warmly, ask them to upload and say 'uploaded' when done
- REJECTED: apologise genuinely, suggest lower amount if possible

STEP 7 - SALARY SLIP (if needed)
- When customer says uploaded: call run_underwriting_with_salary_slip

STEP 8 - SANCTION LETTER
- Share pdf_url as: "Download your sanction letter here: [url]"
- Congratulate them warmly and personally
- After congratulating them, add these next steps naturally in your message:
  "Here's what happens next:
  1. Our team will reach out to you at [email from KYC] within 24 hours to complete the documentation
  2. The loan amount will be disbursed to your account within 2-3 working days after document verification
  3. Your first EMI will be due 30 days from disbursement"
- Then ask warmly: "Is there anything else you'd like to know about your loan or the next steps?"
- If they have follow up questions, answer them using your loan knowledge
- If they say no or thank you or goodbye, close the conversation warmly:
  "It was wonderful helping you today! You're all set — our team will take it from here. Wishing you all the very best. Take care!"
- NEVER abruptly end the conversation after the sanction letter

ABSOLUTE RULES — NEVER BREAK THESE:
- NEVER call the customer "Tia" — Tia is YOU. Use customer's actual first name from KYC.
- NEVER ask for information you already have
- NEVER skip the KYC confirmation step
- NEVER call run_underwriting before KYC is confirmed by customer
- NEVER fabricate a PDF URL — only use exact pdf_url from generate_sanction_letter result
- NEVER mention tool names, backend processes, or technical operations
- NEVER include JSON or raw data in your response
- NEVER ask more than ONE question at a time
- NEVER confuse lakhs with raw rupees — 1 lakh = 100,000, so 40 lakhs = 4,000,000. Always pass full rupee amounts to tools.
- Keep responses to 3-5 sentences for most messages
- For hesitant or emotional customers: up to 8 sentences, address emotion first
- For number questions: always calculate and show actual figures"""

    # ── Live session context ──────────────────────────────────────────────────
    ctx_lines = []
    if customer:
        c    = customer
        rate = _get_rate(c.get("credit_score", 750))
        ctx_lines.append("\nCURRENT SESSION — DO NOT ASK FOR THIS AGAIN:")
        ctx_lines.append(f"Customer name     : {c.get('name')}  <- address by first name only")
        ctx_lines.append(f"Phone             : {state.get('phone')}")
        ctx_lines.append(f"Credit score      : {c.get('credit_score')} -> interest rate = {rate}%")
        ctx_lines.append(f"Pre-approved limit: Rs.{c.get('pre_approved_limit'):,}")
        ctx_lines.append(f"Monthly salary    : Rs.{c.get('monthly_salary'):,}")
        ctx_lines.append(f"Employer          : {c.get('employer')}")
        ctx_lines.append(f"Address           : {c.get('address')}")
        ctx_lines.append(f"PAN               : {c.get('pan')}")
        ctx_lines.append(f"KYC status        : VERIFIED")
        ctx_lines.append(f"KYC confirmed     : {state.get('kyc_confirmed', False)}")
    if state.get("loan_amount"):
        ctx_lines.append(f"Loan amount       : Rs.{state['loan_amount']:,}")
    if state.get("tenure_months"):
        ctx_lines.append(f"Tenure            : {state['tenure_months']} months ({state['tenure_months']//12} years)")
    if uw_result:
        ctx_lines.append(f"Underwriting      : {uw_result}")
    if state.get("salary_slip_uploaded"):
        ctx_lines.append("Salary slip       : uploaded")
    if state.get("pdf_url"):
        ctx_lines.append(f"Sanction PDF URL  : {state['pdf_url']}  <- use this exact URL, do not modify it")

    return prompt + "\n".join(ctx_lines)

# ── Groq call with key rotation ───────────────────────────────────────────────
def call_groq(messages, tools=None):
    payload = {
        "model":       GROQ_MODEL,
        "messages":    messages,
        "temperature": 0.45,
        "max_tokens":  400,
    }
    if tools:
        payload["tools"]       = tools
        payload["tool_choice"] = "auto"

    keys = _GROQ_KEYS if _GROQ_KEYS else []
    if not keys:
        raise Exception("No Groq API keys configured")

    # Try each key, cycling through all of them on 429
    total_attempts = len(keys) * 2
    for attempt in range(total_attempts):
        api_key = keys[attempt % len(keys)]
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type":  "application/json",
            },
            json=payload,
            timeout=25,
        )
        if r.status_code == 429:
            print(f"Key {attempt % len(keys) + 1} rate limited, trying next key...")
            time.sleep(1)
            continue
        r.raise_for_status()
        return r.json()

    raise Exception("All Groq keys rate limited — please try again in a moment")

# ── Main handler ──────────────────────────────────────────────────────────────
def lambda_handler(event, context):
    body = json.loads(event.get("body", "{}"))
    msg  = body.get("message", "").strip()
    sid  = body.get("sessionId", "demo-user")

    if not msg:
        return _respond(
            "Hi! I'm Tia, your loan advisor at Loanify. "
            "I can help you get a personalised loan offer and your sanction letter — all right here in chat. "
            "What kind of loan are you looking for?",
            sid
        )

    state = get_session(sid)

    # Detect salary slip upload confirmation
    if (
        state.get("underwriting_result") == "PENDING_SALARY_SLIP"
        and any(k in msg.lower() for k in ["uploaded", "done", "sent", "submitted", "completed", "upload done"])
    ):
        state["salary_slip_uploaded"] = True
        save_session(sid, state)

    # Detect KYC confirmation
    if (
        state.get("customer")
        and not state.get("kyc_confirmed")
        and any(k in msg.lower() for k in ["yes", "correct", "right", "confirmed", "looks good", "that's right", "yep", "yup", "ok", "okay", "sure", "confirm"])
    ):
        state["kyc_confirmed"] = True
        save_session(sid, state)

    # Build message list for Groq
    messages = [{"role": "system", "content": build_system_prompt(state)}]
    messages.extend(state["history"])
    messages.append({"role": "user", "content": msg})

    # ── Agentic tool-calling loop ─────────────────────────────────────────────
    final_reply = "I'm here to help — could you tell me a bit more?"
    rounds = 0

    while rounds < MAX_ROUNDS:
        if rounds > 0:
            time.sleep(1)  # brief pause between rounds to avoid rate limiting
        try:
            resp = call_groq(messages, tools=TOOLS)
        except Exception as e:
            print(f"Groq error: {e}")
            final_reply = "I'm having a little trouble right now — please try again in a moment!"
            break

        choice = resp["choices"][0]
        finish = choice["finish_reason"]
        lmsg   = choice["message"]

        if finish == "tool_calls":
            tool_calls = lmsg.get("tool_calls", [])
            messages.append({
                "role":       "assistant",
                "content":    lmsg.get("content") or "",
                "tool_calls": tool_calls,
            })
            for tc in tool_calls:
                name   = tc["function"]["name"]
                args   = json.loads(tc["function"]["arguments"] or "{}")
                result = execute_tool(name, args, state, sid)
                print(f"[TOOL RESULT] {result[:400]}")
                messages.append({
                    "role":         "tool",
                    "tool_call_id": tc["id"],
                    "content":      result,
                })
            rounds += 1

        else:
            final_reply = lmsg.get("content", "I'm here to help.")
            break

    # ── Ensure PDF URL is never lost or truncated ─────────────────────────────
    #if state.get("pdf_url") and state["pdf_url"] not in final_reply:
    #    final_reply += f"\n\nDownload your sanction letter here: {state['pdf_url']}"
    # ── Ensure PDF URL is clean and not duplicated ────────────────────────────

    if state.get("pdf_url"):
    # Strip any URL the LLM may have included (mangled or not) and inject the clean one
        import re as _re
        final_reply = _re.sub(r'https?://\S+', '', final_reply).strip()
        final_reply += f"\n\nDownload your sanction letter here: {state['pdf_url']}"

    # Save history (keep last 40 turns to avoid token overflow)
    state["history"].append({"role": "user",      "content": msg})
    state["history"].append({"role": "assistant",  "content": final_reply})
    if len(state["history"]) > 80:
        state["history"] = state["history"][-80:]

    save_session(sid, state)
    return _respond(final_reply, sid)

def _respond(text, sid):
    return {
        "statusCode": 200,
        "headers": {
            "Content-Type":                "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Allow-Methods": "OPTIONS,POST",
        },
        "body": json.dumps({"reply": text, "sessionId": sid}),
    }
