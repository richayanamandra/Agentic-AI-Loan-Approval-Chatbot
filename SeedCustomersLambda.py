"""
SeedCustomersLambda.py
Run ONCE to populate DynamoDB with synthetic customer data.
Invoke manually from AWS console or CLI.
"""
import json
import boto3
from decimal import Decimal

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table("loan_customers")

CUSTOMERS = [
    {
        "phone": "9876543210",
        "name": "Rahul Sharma",
        "age": 32,
        "city": "Mumbai",
        "email": "rahul.sharma@email.com",
        "address": "42 Andheri West, Mumbai - 400053",
        "credit_score": 780,
        "pre_approved_limit": 1500000,
        "monthly_salary": 85000,
        "existing_loans": "Car loan ₹4L outstanding",
        "employer": "Infosys Ltd",
        "pan": "ABCPS1234D",
    },
    {
        "phone": "9812345678",
        "name": "Priya Mehta",
        "age": 28,
        "city": "Bangalore",
        "email": "priya.mehta@email.com",
        "address": "15 Koramangala 4th Block, Bangalore - 560034",
        "credit_score": 820,
        "pre_approved_limit": 2000000,
        "monthly_salary": 120000,
        "existing_loans": "None",
        "employer": "Wipro Technologies",
        "pan": "BCQPM5678E",
    },
    {
        "phone": "9923456789",
        "name": "Amit Patel",
        "age": 45,
        "city": "Ahmedabad",
        "email": "amit.patel@email.com",
        "address": "7 Satellite Road, Ahmedabad - 380015",
        "credit_score": 650,
        "pre_approved_limit": 800000,
        "monthly_salary": 60000,
        "existing_loans": "Home loan ₹20L outstanding",
        "employer": "Self-employed",
        "pan": "CDRAP9012F",
    },
    {
        "phone": "9934567890",
        "name": "Sneha Reddy",
        "age": 35,
        "city": "Hyderabad",
        "email": "sneha.reddy@email.com",
        "address": "22 Banjara Hills Road 12, Hyderabad - 500034",
        "credit_score": 760,
        "pre_approved_limit": 1200000,
        "monthly_salary": 95000,
        "existing_loans": "Personal loan ₹2L outstanding",
        "employer": "Amazon India",
        "pan": "DEQSR3456G",
    },
    {
        "phone": "9845678901",
        "name": "Vikram Singh",
        "age": 38,
        "city": "Delhi",
        "email": "vikram.singh@email.com",
        "address": "88 Vasant Kunj Sector C, New Delhi - 110070",
        "credit_score": 710,
        "pre_approved_limit": 1000000,
        "monthly_salary": 75000,
        "existing_loans": "None",
        "employer": "HCL Technologies",
        "pan": "EFRTS7890H",
    },
    {
        "phone": "9756789012",
        "name": "Meera Iyer",
        "age": 30,
        "city": "Chennai",
        "email": "meera.iyer@email.com",
        "address": "5 Anna Nagar East, Chennai - 600102",
        "credit_score": 800,
        "pre_approved_limit": 1800000,
        "monthly_salary": 110000,
        "existing_loans": "None",
        "employer": "TCS",
        "pan": "FGUMI1234I",
    },
    {
        "phone": "9667890123",
        "name": "Rohit Gupta",
        "age": 42,
        "city": "Pune",
        "email": "rohit.gupta@email.com",
        "address": "33 Kothrud, Pune - 411038",
        "credit_score": 730,
        "pre_approved_limit": 900000,
        "monthly_salary": 65000,
        "existing_loans": "Car loan ₹6L outstanding",
        "employer": "Bajaj Auto",
        "pan": "GHNRG5678J",
    },
    {
        "phone": "9578901234",
        "name": "Anita Desai",
        "age": 27,
        "city": "Kolkata",
        "email": "anita.desai@email.com",
        "address": "12 Salt Lake Sector 5, Kolkata - 700091",
        "credit_score": 690,
        "pre_approved_limit": 700000,
        "monthly_salary": 55000,
        "existing_loans": "None",
        "employer": "Cognizant",
        "pan": "HIJAD9012K",
    },
    {
        "phone": "9489012345",
        "name": "Suresh Nair",
        "age": 50,
        "city": "Kochi",
        "email": "suresh.nair@email.com",
        "address": "6 Edapally, Kochi - 682024",
        "credit_score": 750,
        "pre_approved_limit": 1100000,
        "monthly_salary": 80000,
        "existing_loans": "Home loan ₹35L outstanding",
        "employer": "Kerala Government",
        "pan": "IJKSN3456L",
    },
    {
        "phone": "9390123456",
        "name": "Kavya Joshi",
        "age": 26,
        "city": "Jaipur",
        "email": "kavya.joshi@email.com",
        "address": "19 Malviya Nagar, Jaipur - 302017",
        "credit_score": 840,
        "pre_approved_limit": 2500000,
        "monthly_salary": 150000,
        "existing_loans": "None",
        "employer": "Accenture India",
        "pan": "JLTKJ7890M",
    },
]


def lambda_handler(event, context):
    seeded = []
    for customer in CUSTOMERS:
        # Convert ints to Decimal for DynamoDB
        item = {k: Decimal(str(v)) if isinstance(v, int) else v for k, v in customer.items()}
        table.put_item(Item=item)
        seeded.append(customer["name"])

    return {
        "statusCode": 200,
        "body": json.dumps({"message": "Seeded successfully", "customers": seeded}),
    }
