import json

def lambda_handler(event, context):
    """
    Minimal KYC verification worker
    Prototype version
    """

    # Simulate KYC verification
    response = {
        "kyc_status": "VERIFIED",
        "verified_fields": [
            "name",
            "phone",
            "address"
        ]
    }

    return {
        "statusCode": 200,
        "body": json.dumps(response)
    }
