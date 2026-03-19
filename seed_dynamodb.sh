#!/bin/bash

# ── Create the loan_customers table (skip if already exists) ──────────────────
aws dynamodb create-table \
  --table-name loan_customers \
  --attribute-definitions AttributeName=phone,AttributeType=S \
  --key-schema AttributeName=phone,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region us-east-1

# ── Create the loan_sessions table (skip if already exists) ───────────────────
aws dynamodb create-table \
  --table-name loan_sessions \
  --attribute-definitions AttributeName=session_id,AttributeType=S \
  --key-schema AttributeName=session_id,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region us-east-1

# Wait for tables to be active
echo "Waiting for tables to be active..."
aws dynamodb wait table-exists --table-name loan_customers --region us-east-1
aws dynamodb wait table-exists --table-name loan_sessions --region us-east-1
echo "Tables ready."

# ── Enable TTL on loan_sessions ────────────────────────────────────────────────
aws dynamodb update-time-to-live \
  --table-name loan_sessions \
  --time-to-live-specification "Enabled=true,AttributeName=ttl" \
  --region us-east-1

# ══════════════════════════════════════════════════════════════════════════════
# SEED 10 CUSTOMERS
# ══════════════════════════════════════════════════════════════════════════════

echo "Seeding customers..."

# 1. Rahul Sharma — Mumbai, 780 score, ₹15L pre-approved
aws dynamodb put-item --table-name loan_customers --region us-east-1 --item '{
  "phone":              {"S": "9876543210"},
  "name":               {"S": "Rahul Sharma"},
  "age":                {"N": "32"},
  "city":               {"S": "Mumbai"},
  "email":              {"S": "rahul.sharma@email.com"},
  "address":            {"S": "42 Andheri West, Mumbai - 400053"},
  "credit_score":       {"N": "780"},
  "pre_approved_limit": {"N": "1500000"},
  "monthly_salary":     {"N": "85000"},
  "existing_loans":     {"S": "Car loan 4L outstanding"},
  "employer":           {"S": "Infosys Ltd"},
  "pan":                {"S": "ABCPS1234D"}
}'

# 2. Tia Mehta — Bangalore, 820 score, ₹20L pre-approved
aws dynamodb put-item --table-name loan_customers --region us-east-1 --item '{
  "phone":              {"S": "9812345678"},
  "name":               {"S": "Tia Mehta"},
  "age":                {"N": "28"},
  "city":               {"S": "Bangalore"},
  "email":              {"S": "Tia.mehta@email.com"},
  "address":            {"S": "15 Koramangala 4th Block, Bangalore - 560034"},
  "credit_score":       {"N": "820"},
  "pre_approved_limit": {"N": "2000000"},
  "monthly_salary":     {"N": "120000"},
  "existing_loans":     {"S": "None"},
  "employer":           {"S": "Wipro Technologies"},
  "pan":                {"S": "BCQPM5678E"}
}'

# 3. Amit Patel — Ahmedabad, 650 score (WILL BE REJECTED)
aws dynamodb put-item --table-name loan_customers --region us-east-1 --item '{
  "phone":              {"S": "9923456789"},
  "name":               {"S": "Amit Patel"},
  "age":                {"N": "45"},
  "city":               {"S": "Ahmedabad"},
  "email":              {"S": "amit.patel@email.com"},
  "address":            {"S": "7 Satellite Road, Ahmedabad - 380015"},
  "credit_score":       {"N": "650"},
  "pre_approved_limit": {"N": "800000"},
  "monthly_salary":     {"N": "60000"},
  "existing_loans":     {"S": "Home loan 20L outstanding"},
  "employer":           {"S": "Self-employed"},
  "pan":                {"S": "CDRAP9012F"}
}'

# 4. Sneha Reddy — Hyderabad, 760 score, ₹12L pre-approved
aws dynamodb put-item --table-name loan_customers --region us-east-1 --item '{
  "phone":              {"S": "9934567890"},
  "name":               {"S": "Sneha Reddy"},
  "age":                {"N": "35"},
  "city":               {"S": "Hyderabad"},
  "email":              {"S": "sneha.reddy@email.com"},
  "address":            {"S": "22 Banjara Hills Road 12, Hyderabad - 500034"},
  "credit_score":       {"N": "760"},
  "pre_approved_limit": {"N": "1200000"},
  "monthly_salary":     {"N": "95000"},
  "existing_loans":     {"S": "Personal loan 2L outstanding"},
  "employer":           {"S": "Amazon India"},
  "pan":                {"S": "DEQSR3456G"}
}'

# 5. Vikram Singh — Delhi, 710 score, ₹10L pre-approved
aws dynamodb put-item --table-name loan_customers --region us-east-1 --item '{
  "phone":              {"S": "9845678901"},
  "name":               {"S": "Vikram Singh"},
  "age":                {"N": "38"},
  "city":               {"S": "Delhi"},
  "email":              {"S": "vikram.singh@email.com"},
  "address":            {"S": "88 Vasant Kunj Sector C, New Delhi - 110070"},
  "credit_score":       {"N": "710"},
  "pre_approved_limit": {"N": "1000000"},
  "monthly_salary":     {"N": "75000"},
  "existing_loans":     {"S": "None"},
  "employer":           {"S": "HCL Technologies"},
  "pan":                {"S": "EFRTS7890H"}
}'

# 6. Meera Iyer — Chennai, 800 score, ₹18L pre-approved
aws dynamodb put-item --table-name loan_customers --region us-east-1 --item '{
  "phone":              {"S": "9756789012"},
  "name":               {"S": "Meera Iyer"},
  "age":                {"N": "30"},
  "city":               {"S": "Chennai"},
  "email":              {"S": "meera.iyer@email.com"},
  "address":            {"S": "5 Anna Nagar East, Chennai - 600102"},
  "credit_score":       {"N": "800"},
  "pre_approved_limit": {"N": "1800000"},
  "monthly_salary":     {"N": "110000"},
  "existing_loans":     {"S": "None"},
  "employer":           {"S": "TCS"},
  "pan":                {"S": "FGUMI1234I"}
}'

# 7. Rohit Gupta — Pune, 730 score, ₹9L pre-approved
aws dynamodb put-item --table-name loan_customers --region us-east-1 --item '{
  "phone":              {"S": "9667890123"},
  "name":               {"S": "Rohit Gupta"},
  "age":                {"N": "42"},
  "city":               {"S": "Pune"},
  "email":              {"S": "rohit.gupta@email.com"},
  "address":            {"S": "33 Kothrud, Pune - 411038"},
  "credit_score":       {"N": "730"},
  "pre_approved_limit": {"N": "900000"},
  "monthly_salary":     {"N": "65000"},
  "existing_loans":     {"S": "Car loan 6L outstanding"},
  "employer":           {"S": "Bajaj Auto"},
  "pan":                {"S": "GHNRG5678J"}
}'

# 8. Anita Desai — Kolkata, 690 score (borderline reject)
aws dynamodb put-item --table-name loan_customers --region us-east-1 --item '{
  "phone":              {"S": "9578901234"},
  "name":               {"S": "Anita Desai"},
  "age":                {"N": "27"},
  "city":               {"S": "Kolkata"},
  "email":              {"S": "anita.desai@email.com"},
  "address":            {"S": "12 Salt Lake Sector 5, Kolkata - 700091"},
  "credit_score":       {"N": "690"},
  "pre_approved_limit": {"N": "700000"},
  "monthly_salary":     {"N": "55000"},
  "existing_loans":     {"S": "None"},
  "employer":           {"S": "Cognizant"},
  "pan":                {"S": "HIJAD9012K"}
}'

# 9. Suresh Nair — Kochi, 750 score, ₹11L pre-approved
aws dynamodb put-item --table-name loan_customers --region us-east-1 --item '{
  "phone":              {"S": "9489012345"},
  "name":               {"S": "Suresh Nair"},
  "age":                {"N": "50"},
  "city":               {"S": "Kochi"},
  "email":              {"S": "suresh.nair@email.com"},
  "address":            {"S": "6 Edapally, Kochi - 682024"},
  "credit_score":       {"N": "750"},
  "pre_approved_limit": {"N": "1100000"},
  "monthly_salary":     {"N": "80000"},
  "existing_loans":     {"S": "Home loan 35L outstanding"},
  "employer":           {"S": "Kerala Government"},
  "pan":                {"S": "IJKSN3456L"}
}'

# 10. Kavya Joshi — Jaipur, 840 score, ₹25L pre-approved (best profile)
aws dynamodb put-item --table-name loan_customers --region us-east-1 --item '{
  "phone":              {"S": "9390123456"},
  "name":               {"S": "Kavya Joshi"},
  "age":                {"N": "26"},
  "city":               {"S": "Jaipur"},
  "email":              {"S": "kavya.joshi@email.com"},
  "address":            {"S": "19 Malviya Nagar, Jaipur - 302017"},
  "credit_score":       {"N": "840"},
  "pre_approved_limit": {"N": "2500000"},
  "monthly_salary":     {"N": "150000"},
  "existing_loans":     {"S": "None"},
  "employer":           {"S": "Accenture India"},
  "pan":                {"S": "JLTKJ7890M"}
}'

echo ""
echo "✅ All 10 customers seeded successfully."
echo ""
echo "Verifying count..."
aws dynamodb scan --table-name loan_customers --select COUNT --region us-east-1 \
  --query 'Count' --output text | xargs -I{} echo "  loan_customers rows: {}"
