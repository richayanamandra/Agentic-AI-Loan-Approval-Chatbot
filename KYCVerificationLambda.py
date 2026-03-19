"""
KYCVerificationLambda.py

Worker Agent: KYC Verification
- Looks up customer in DynamoDB loan_customers table by phone number
- Returns verified customer profile if found
- Returns FAILED if not found (simulates CRM lookup)

Called by Master Agent with: { "phone": "9876543210" }
"""

import json
import boto3
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table("loan_customers")


def lambda_handler(event, context):
    phone = str(event.get("phone", "")).strip()

    if not phone:
        return _respond(
            {
                "kyc_status": "FAILED",
                "reason": "Phone number not provided",
                "customer": None,
            }
        )

    # Query DynamoDB (CRM lookup)
    response = table.get_item(Key={"phone": phone})
    item = response.get("Item")

    if not item:
        return _respond(
            {
                "kyc_status": "FAILED",
                "reason": f"No customer record found for phone {phone}. Not in our CRM.",
                "customer": None,
            }
        )

    # Build safe customer profile (convert Decimal → int/float for JSON)
    customer = _deserialize(item)

    return _respond(
        {
            "kyc_status": "VERIFIED",
            "verified_fields": ["name", "phone", "address", "pan", "employer"],
            "customer": {
                "name": customer["name"],
                "age": customer["age"],
                "city": customer["city"],
                "email": customer["email"],
                "address": customer["address"],
                "employer": customer["employer"],
                "pan": customer["pan"],
                "monthly_salary": customer["monthly_salary"],
                "credit_score": customer["credit_score"],
                "pre_approved_limit": customer["pre_approved_limit"],
                "existing_loans": customer["existing_loans"],
            },
        }
    )


def _deserialize(item):
    """Convert DynamoDB Decimal types to Python native types."""
    from decimal import Decimal

    result = {}
    for k, v in item.items():
        if isinstance(v, Decimal):
            result[k] = int(v) if v == int(v) else float(v)
        else:
            result[k] = v
    return result


def _respond(body):
    return {
        "statusCode": 200,
        "body": json.dumps(body),
    }
