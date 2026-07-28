import os
import re
import pandas as pd
import smtplib
from urllib.parse import urlparse
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from datetime import datetime

# --- Configuration ---
# Reads from environment variables. Do not hardcode email passwords in code.
SENDER_EMAIL    = os.environ.get("SENDER_EMAIL",    "")
SENDER_PASSWORD = os.environ.get("SENDER_PASSWORD", "")
RECEIVER_EMAIL  = os.environ.get("RECEIVER_EMAIL",  "")
BASE_DIR        = os.path.dirname(os.path.abspath(__file__))
EXCEL_FILE      = os.path.join(BASE_DIR, "enrollment_data.xlsx")
CSV_FILE        = os.path.join(BASE_DIR, "enrollment_report.csv")
DOCS_CSV_FILE   = os.path.join(BASE_DIR, "docs", "enrollment_report.csv")

def extract_course_id(url):
    """Extracts course ID from NPTEL URL. e.g. noc24_cs01 from the URL."""
    try:
        match = re.search(r'(noc\d{2}_[a-z]+\d+)', str(url), re.IGNORECASE)
        if match:
            return match.group(1)
        parts = [p for p in urlparse(str(url)).path.split('/') if p]
        return parts[-1] if parts else url
    except:
        return url

def send_report():
    try:
        if not SENDER_EMAIL or not SENDER_PASSWORD or not RECEIVER_EMAIL:
            raise ValueError(
                "Missing email settings. Set SENDER_EMAIL, SENDER_PASSWORD, and RECEIVER_EMAIL."
            )

        # 1. Load enrollment data
        if os.path.exists(EXCEL_FILE):
            df = pd.read_excel(EXCEL_FILE)
        elif os.path.exists(DOCS_CSV_FILE):
            df = pd.read_csv(DOCS_CSV_FILE)
        elif os.path.exists(CSV_FILE):
            df = pd.read_csv(CSV_FILE)
        else:
            raise FileNotFoundError("No enrollment report found to email")

        # 2. Ensure Course ID exists
        if 'Course_ID' not in df.columns and 'Course_URL' in df.columns:
            df['Course_ID'] = df['Course_URL'].apply(extract_course_id)
        df = df[df['Course_ID'].astype(str).ne('TOTAL')].copy()

        # 3. Build CSV with: Course_ID | Learners_Enrolled | Total row
        csv_df = df[['Course_ID', 'Learners_Enrolled']].copy()
        valid_enrollments = pd.to_numeric(csv_df['Learners_Enrolled'], errors='coerce').fillna(0)
        total_enrollment  = int(valid_enrollments.sum())
        total_courses     = len(csv_df)
        run_time          = datetime.now().strftime("%d %b %Y, %I:%M %p")

        # Add total row at the bottom
        total_row = pd.DataFrame([['TOTAL', total_enrollment]], columns=['Course_ID', 'Learners_Enrolled'])
        csv_df = pd.concat([csv_df, total_row], ignore_index=True)
        csv_df.to_csv(CSV_FILE, index=False)

        # 4. Build HTML email body
        html_content = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; color: #333333; margin: 0; padding: 0; }}
                .container {{ width: 80%; margin: 20px auto; }}
                .header {{ background-color: #004d99; color: white; padding: 18px; text-align: center; border-radius: 5px 5px 0 0; }}
                .header h2 {{ margin: 0; font-size: 20px; }}
                .summary-box {{ background-color: #f0f4ff; border-left: 5px solid #004d99; padding: 15px 20px; margin: 20px 0; border-radius: 3px; }}
                .summary-box p {{ margin: 6px 0; font-size: 15px; }}
                .body-text {{ font-size: 15px; margin: 10px 0; }}
                .footer {{ margin-top: 30px; font-size: 12px; color: #999; text-align: center; }}
            </style>
        </head>
        <body>
            <div class="container">

                <div class="header">
                    <h2>Course Wise Enrollment Count - 2026</h2>
                </div>

                <p class="body-text">Dear Sir/Ma'am,</p>
                <p class="body-text">Please find the below Total Course wise Enrollment count - 2026.</p>

                <div class="summary-box">
                    <p><strong>&#128197; Date &amp; Time Run:</strong> {run_time}</p>
                    <p><strong>&#128218; Total Courses Tracked:</strong> {total_courses}</p>
                    <p><strong>&#128101; Total Enrollment Count:</strong> {total_enrollment:,}</p>
                </div>

                <p class="body-text">The complete Course ID wise breakdown is attached as a CSV file with this email.</p>

                <p class="body-text">
                    Regards,<br>
                    <strong>NPTEL</strong>
                </p>

                <div class="footer">
                    <p>This is an automated report. Please do not reply to this email.</p>
                </div>

            </div>
        </body>
        </html>
        """

        # 5. Setup email message
        msg = MIMEMultipart()
        msg['Subject'] = "Course Wise Enrollment Count - 2026"
        msg['From']    = SENDER_EMAIL
        msg['To']      = RECEIVER_EMAIL

        msg.attach(MIMEText(html_content, 'html'))

        # 6. Attach CSV file
        with open(CSV_FILE, "rb") as f:
            attachment = MIMEApplication(f.read(), _subtype="csv")
            attachment.add_header('Content-Disposition', 'attachment', filename=os.path.basename(CSV_FILE))
            msg.attach(attachment)

        # 7. Send via Gmail SMTP
        print("Connecting to email server...")
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(msg)

        print(f"Success! Email sent at {run_time}")

    except Exception as e:
        print(f"Error sending email: {e}")

# Run
if __name__ == "__main__":
    send_report()

