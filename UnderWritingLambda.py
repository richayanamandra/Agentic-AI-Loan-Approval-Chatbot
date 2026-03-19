"""
UnderwritingLambda.py

Worker Agent: Underwriting / Credit Eligibility
- Uses customer profile fetched during KYC (passed in by Master Agent)
- Applies real Tata Capital-style eligibility rules
- Handles salary slip verification flow for borderline cases

Input (from Master Agent):
{
    "customer": { ...KYC profile... },
    "loan_amount": 1500000,
    "tenure_months": 60,
    "emi": 34000,
    "salary_slip_uploaded": false   # optional, for 2x limit cases
}

Output:
{
    "decision": "APPROVED" | "REJECTED" | "PENDING_SALARY_SLIP",
    "reason": "...",
    "approved_amount": 1500000,
    "interest_rate": 13.5,
    "tenure_months": 60,
    "emi": 34000,
    "credit_score": 780,
    "sanction_details": { ... }   # only if APPROVED
}
"""

import json
import math

# Interest rate matrix by credit score
def get_interest_rate(credit_score):
    if credit_score >= 800:
        return 11.5
    elif credit_score >= 750:
        return 12.5
    elif credit_score >= 700:
        return 13.5
    else:
        return None  # Not eligible


def calculate_emi(principal, annual_rate, months):
    r = annual_rate / (12 * 100)
    if r == 0:
        return principal / months
    return math.ceil((principal * r * (1 + r) ** months) / ((1 + r) ** months - 1))


def lambda_handler(event, context):
    customer = event.get("customer", {})
    loan_amount = int(event.get("loan_amount", 0))
    tenure_months = int(event.get("tenure_months", 60))
    salary_slip_uploaded = event.get("salary_slip_uploaded", False)

    # ── Extract customer financials ──────────────────────────────────────────
    credit_score = int(customer.get("credit_score", 0))
    pre_approved_limit = int(customer.get("pre_approved_limit", 0))
    monthly_salary = int(customer.get("monthly_salary", 0))
    customer_name = customer.get("name", "Customer")

    # ── Rule 0: Valid credit score ───────────────────────────────────────────
    if credit_score < 700:
        return _respond({
            "decision": "REJECTED",
            "reason": (
                f"Credit score of {credit_score} is below our minimum threshold of 700. "
                "We recommend improving your credit profile and reapplying."
            ),
            "credit_score": credit_score,
        })

    interest_rate = get_interest_rate(credit_score)
    emi = calculate_emi(loan_amount, interest_rate, tenure_months)

    # ── Rule 1: Within pre-approved limit → instant approval ────────────────
    if loan_amount <= pre_approved_limit:
        return _respond({
            "decision": "APPROVED",
            "reason": f"Loan amount is within your pre-approved limit of ₹{pre_approved_limit:,}.",
            "approved_amount": loan_amount,
            "interest_rate": interest_rate,
            "tenure_months": tenure_months,
            "emi": emi,
            "credit_score": credit_score,
            "sanction_details": _build_sanction(customer, loan_amount, interest_rate, tenure_months, emi),
        })

    # ── Rule 2: Between 1x and 2x pre-approved → needs salary slip ──────────
    if loan_amount <= 2 * pre_approved_limit:
        max_allowed_emi = 0.5 * monthly_salary

        if not salary_slip_uploaded:
            return _respond({
                "decision": "PENDING_SALARY_SLIP",
                "reason": (
                    f"Your requested amount of ₹{loan_amount:,} exceeds your pre-approved limit "
                    f"of ₹{pre_approved_limit:,}. To process this, we need a salary slip upload to verify income. "
                    f"Your estimated EMI would be ₹{emi:,}/month."
                ),
                "required_emi": emi,
                "max_allowed_emi": int(max_allowed_emi),
                "credit_score": credit_score,
            })

        # Salary slip was uploaded — check affordability
        if emi <= max_allowed_emi:
            return _respond({
                "decision": "APPROVED",
                "reason": (
                    f"Approved based on income verification. "
                    f"EMI of ₹{emi:,} is within 50% of monthly salary (₹{monthly_salary:,})."
                ),
                "approved_amount": loan_amount,
                "interest_rate": interest_rate,
                "tenure_months": tenure_months,
                "emi": emi,
                "credit_score": credit_score,
                "sanction_details": _build_sanction(customer, loan_amount, interest_rate, tenure_months, emi),
            })
        else:
            # Suggest a lower amount that would be approved
            max_affordable_loan = _max_affordable_loan(max_allowed_emi, interest_rate, tenure_months)
            return _respond({
                "decision": "REJECTED",
                "reason": (
                    f"EMI of ₹{emi:,} exceeds 50% of monthly salary (max affordable EMI: ₹{int(max_allowed_emi):,}). "
                    f"We can approve up to ₹{max_affordable_loan:,} with this tenure."
                ),
                "credit_score": credit_score,
                "suggested_max_amount": max_affordable_loan,
            })

    # ── Rule 3: Above 2x pre-approved → reject ──────────────────────────────
    return _respond({
        "decision": "REJECTED",
        "reason": (
            f"Requested amount of ₹{loan_amount:,} exceeds twice your pre-approved limit "
            f"(₹{2 * pre_approved_limit:,}). Please consider a lower loan amount."
        ),
        "credit_score": credit_score,
        "maximum_eligible": 2 * pre_approved_limit,
    })


def _max_affordable_loan(max_emi, annual_rate, months):
    r = annual_rate / (12 * 100)
    if r == 0:
        return int(max_emi * months)
    principal = max_emi * ((1 + r) ** months - 1) / (r * (1 + r) ** months)
    # Round down to nearest 50,000
    return int(principal // 50000) * 50000


def _build_sanction(customer, amount, rate, tenure, emi):
    import uuid
    import datetime

    sanction_id = f"TC-PL-{datetime.datetime.now().year}-{str(uuid.uuid4())[:6].upper()}"
    return {
        "sanction_id": sanction_id,
        "customer_name": customer.get("name"),
        "customer_address": customer.get("address"),
        "customer_pan": customer.get("pan"),
        "customer_employer": customer.get("employer"),
        "loan_amount": amount,
        "interest_rate": rate,
        "tenure_months": tenure,
        "emi": emi,
        "sanction_date": datetime.datetime.now().strftime("%d %B %Y"),
        "valid_until": (datetime.datetime.now() + datetime.timedelta(days=30)).strftime("%d %B %Y"),
    }


def _respond(body):
    return {
        "statusCode": 200,
        "body": json.dumps(body),
    }
