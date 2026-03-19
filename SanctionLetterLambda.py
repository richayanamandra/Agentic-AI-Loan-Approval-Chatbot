import json, os, io, boto3
from fpdf import FPDF

S3_BUCKET = os.environ.get("SANCTION_BUCKET", "sanction-letters-bucket")
s3_client = boto3.client("s3")

def lambda_handler(event, context):
    sd = event.get("sanction_details", {})
    session_id = event.get("session_id", "unknown")
    if not sd:
        return _respond({"error": "No sanction details provided"}, 400)
    try:
        pdf_bytes = generate_pdf(sd)
    except Exception as e:
        return _respond({"error": f"PDF generation failed: {str(e)}"}, 500)
    s3_key = f"sanction-letters/{sd['sanction_id']}-{session_id}.pdf"
    try:
        s3_client.put_object(Bucket=S3_BUCKET, Key=s3_key, Body=pdf_bytes,
            ContentType="application/pdf",
            ContentDisposition=f'attachment; filename="{sd["sanction_id"]}.pdf"')
    except Exception as e:
        return _respond({"error": f"S3 upload failed: {str(e)}"}, 500)
    url = s3_client.generate_presigned_url("get_object",
        Params={"Bucket": S3_BUCKET, "Key": s3_key}, ExpiresIn=604800)
    return _respond({"sanction_id": sd["sanction_id"], "pdf_url": url,
        "customer_name": sd.get("customer_name"),
        "loan_amount": sd.get("loan_amount"), "emi": sd.get("emi")})

def generate_pdf(sd):
    loan_amt   = int(sd["loan_amount"])
    emi        = int(sd["emi"])
    rate       = float(sd["interest_rate"])
    tm         = int(sd["tenure_months"])
    ty         = tm // 12
    tp         = emi * tm
    ti         = tp - loan_amt
    first_name = sd["customer_name"].split()[0]

    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # ── Header band ──────────────────────────────────────────────────────────
    pdf.set_fill_color(0, 48, 135)        # Tata Blue
    pdf.rect(0, 0, 210, 28, "F")
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_xy(0, 6)
    pdf.cell(210, 10, "Loanify", align="C")
    pdf.set_font("Helvetica", "", 9)
    pdf.set_xy(0, 17)
    pdf.cell(210, 6, "Financial Services Limited", align="C")

    # Red accent
    pdf.set_fill_color(200, 16, 46)
    pdf.rect(0, 28, 210, 2, "F")

    # ── Title ─────────────────────────────────────────────────────────────────
    pdf.set_text_color(0, 48, 135)
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_xy(0, 35)
    pdf.cell(210, 10, "LOAN SANCTION LETTER", align="C")

    # ── Meta row ──────────────────────────────────────────────────────────────
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(50, 50, 50)
    pdf.set_xy(15, 48)
    pdf.cell(90, 6, f"Sanction ID: {sd['sanction_id']}")
    pdf.set_xy(105, 48)
    pdf.cell(90, 6, f"Date: {sd['sanction_date']}", align="R")

    # Divider
    pdf.set_draw_color(200, 16, 46)
    pdf.set_line_width(0.5)
    pdf.line(15, 56, 195, 56)

    # ── Addressee ─────────────────────────────────────────────────────────────
    pdf.set_xy(15, 60)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(50, 50, 50)
    pdf.cell(0, 6, "To,")
    pdf.set_xy(15, 67)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, sd["customer_name"])
    pdf.set_xy(15, 74)
    pdf.set_font("Helvetica", "", 9)
    pdf.multi_cell(120, 5, sd.get("customer_address", ""))

    y = pdf.get_y() + 4
    pdf.set_draw_color(180, 180, 180)
    pdf.set_line_width(0.3)
    pdf.line(15, y, 195, y)
    y += 5

    # ── Subject ───────────────────────────────────────────────────────────────
    pdf.set_xy(15, y)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(0, 48, 135)
    pdf.cell(0, 6, f"Subject: Sanction of Personal Loan of Rs.{loan_amt:,}/-")
    y += 10

    pdf.set_xy(15, y)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(50, 50, 50)
    pdf.cell(0, 6, f"Dear {first_name},")
    y += 9

    pdf.set_xy(15, y)
    pdf.set_font("Helvetica", "", 9)
    pdf.multi_cell(180, 5,
        "We are pleased to inform you that Loanify Financial Services Limited has "
        "approved your Personal Loan application. Please find the sanctioned loan details below.")
    y = pdf.get_y() + 5

    # ── Loan details table ────────────────────────────────────────────────────
    pdf.set_xy(15, y)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(0, 48, 135)
    pdf.cell(0, 7, "LOAN DETAILS")
    y += 8

    # Table header
    pdf.set_fill_color(0, 48, 135)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_xy(15, y)
    pdf.cell(80, 8, "Parameter", fill=True)
    pdf.cell(100, 8, "Details", fill=True)
    y += 8

    loan_rows = [
        ("Loan Amount (Principal)", f"Rs.{loan_amt:,}/-"),
        ("Loan Type", "Personal Loan"),
        ("Rate of Interest (p.a.)", f"{rate}% (Reducing Balance)"),
        ("Tenure", f"{tm} Months ({ty} Years)"),
        ("EMI Amount", f"Rs.{emi:,}/- per month"),
        ("Total Interest Payable", f"Rs.{ti:,}/-"),
        ("Total Amount Payable", f"Rs.{tp:,}/-"),
        ("Processing Fee", "1.0% + GST"),
        ("Prepayment Charges", "2% on outstanding (after 12 EMIs)"),
    ]
    for i, (lbl, val) in enumerate(loan_rows):
        fill = i % 2 == 0
        pdf.set_fill_color(245, 245, 245) if fill else pdf.set_fill_color(255, 255, 255)
        pdf.set_text_color(50, 50, 50)
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_xy(15, y)
        pdf.cell(80, 7, lbl, fill=fill)
        pdf.set_font("Helvetica", "", 9)
        pdf.cell(100, 7, val, fill=fill)
        y += 7

    y += 4
    pdf.set_draw_color(180, 180, 180)
    pdf.line(15, y, 195, y)
    y += 5

    # ── Borrower details table ────────────────────────────────────────────────
    pdf.set_xy(15, y)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(0, 48, 135)
    pdf.cell(0, 7, "BORROWER DETAILS")
    y += 8

    pdf.set_fill_color(0, 48, 135)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_xy(15, y)
    pdf.cell(80, 8, "Field", fill=True)
    pdf.cell(100, 8, "Details", fill=True)
    y += 8

    borrower_rows = [
        ("Full Name", sd["customer_name"]),
        ("PAN Number", sd.get("customer_pan", "N/A")),
        ("Employer", sd.get("customer_employer", "N/A")),
        ("Loan Account No.", f"TCPL{sd['sanction_id'][-6:]}"),
        ("Valid Until", sd.get("valid_until", "N/A")),
    ]
    for i, (lbl, val) in enumerate(borrower_rows):
        fill = i % 2 == 0
        pdf.set_fill_color(245, 245, 245) if fill else pdf.set_fill_color(255, 255, 255)
        pdf.set_text_color(50, 50, 50)
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_xy(15, y)
        pdf.cell(80, 7, lbl, fill=fill)
        pdf.set_font("Helvetica", "", 9)
        pdf.cell(100, 7, val, fill=fill)
        y += 7

    y += 4
    pdf.line(15, y, 195, y)
    y += 5

    # ── Terms ─────────────────────────────────────────────────────────────────
    pdf.set_xy(15, y)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(0, 48, 135)
    pdf.cell(0, 7, "TERMS AND CONDITIONS")
    y += 8

    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(50, 50, 50)
    for term in [
        f"1. This sanction letter is valid until {sd.get('valid_until', 'N/A')}.",
        "2. Loan is subject to execution of Loan Agreement and submission of required documents.",
        "3. EMI will be collected via NACH/ECS mandate from your registered bank account.",
        "4. Loanify reserves the right to recall the loan if any information is found false.",
        "5. Late payment charges: 2% per month on overdue EMI amount.",
    ]:
        pdf.set_xy(15, y)
        pdf.cell(0, 5, term)
        y += 5

    y += 8
    pdf.line(15, y, 195, y)
    y += 6

    # ── Signature ─────────────────────────────────────────────────────────────
    pdf.set_xy(15, y)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(50, 50, 50)
    pdf.cell(0, 5, "Authorized Signatory")
    pdf.set_xy(15, y + 6)
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(0, 5, "Loanify Financial Services Ltd. | Digital Banking Division")
    pdf.set_xy(15, y + 12)
    pdf.set_font("Helvetica", "I", 7)
    pdf.set_text_color(130, 130, 130)
    pdf.cell(0, 5, "Digitally generated document - no physical signature required.")

    # ── Footer band ───────────────────────────────────────────────────────────
    pdf.set_fill_color(0, 48, 135)
    pdf.rect(0, 282, 210, 15, "F")
    pdf.set_fill_color(200, 16, 46)
    pdf.rect(0, 280, 210, 2, "F")
    pdf.set_xy(0, 284)
    pdf.set_font("Helvetica", "", 6)
    pdf.set_text_color(170, 187, 221)
    pdf.cell(210, 5,
        "Loanify Financial Services Ltd. | Peninsula Business Park, Mumbai 400013 | 1800-209-6060 | www.loanify.com",
        align="C")

    return bytes(pdf.output())

def _respond(body, status=200):
    return {"statusCode": status, "body": json.dumps(body)}
