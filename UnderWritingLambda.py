import json

def lambda_handler(event, context):
    """
    Dummy underwriting agent for prototype
    Implements Tata Capital-style eligibility rules
    """

    # -------- Extract inputs --------
    loan_type = event.get("loan_type")
    loan_amount = event.get("amount")
    emi = event.get("emi")

    # -------- HOME LOAN: Auto-approve for demo --------
    if loan_type == "HOME":
        return {
            "statusCode": 200,
            "body": json.dumps({
                "decision": "APPROVED",
                "reason": "Home loan approved in prototype flow"
            })
        }

    # -------- Dummy customer profile --------
    credit_score = 780              # out of 900
    preapproved_limit = 1500000     # ₹15 lakhs
    monthly_salary = 80000          # ₹80,000

    # -------- Rule 1: Credit score --------
    if credit_score < 700:
        return {
            "statusCode": 200,
            "body": json.dumps({
                "decision": "REJECTED",
                "reason": "Low credit score"
            })
        }

    # -------- Rule 2: Within pre-approved --------
    if loan_amount <= preapproved_limit:
        return {
            "statusCode": 200,
            "body": json.dumps({
                "decision": "APPROVED",
                "reason": "Within pre-approved limit"
            })
        }

    # -------- Rule 3: Up to 2x pre-approved --------
    if loan_amount <= 2 * preapproved_limit:
        max_allowed_emi = 0.5 * monthly_salary

        if emi <= max_allowed_emi:
            return {
                "statusCode": 200,
                "body": json.dumps({
                    "decision": "APPROVED",
                    "reason": "Affordable based on income"
                })
            }
        else:
            return {
                "statusCode": 200,
                "body": json.dumps({
                    "decision": "REJECTED",
                    "reason": "EMI exceeds affordability"
                })
            }

    # -------- Rule 4: Above eligibility --------
    return {
        "statusCode": 200,
        "body": json.dumps({
            "decision": "REJECTED",
            "reason": "Requested amount exceeds eligibility"
        })
    }
