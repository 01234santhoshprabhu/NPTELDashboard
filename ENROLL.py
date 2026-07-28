import os
import json
import pandas as pd
import requests
import urllib3
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import time
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from html import unescape
from urllib.parse import urlparse

# --- Configuration ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
input_excel  = os.path.join(BASE_DIR, 'courses.xlsx')           # Optional Excel input with Course_URL column
input_csv    = os.path.join(BASE_DIR, 'courses.csv')            # CSV fallback with Course_URL column
output_excel = os.path.join(BASE_DIR, 'enrollment_data.xlsx')   # Output file with enrollment counts
debug_folder = os.path.join(BASE_DIR, 'debug_pages')
MAX_WORKERS = 24
REQUEST_TIMEOUT = 10
BROWSER_RECHECK = os.getenv("BROWSER_RECHECK", "0") == "1"
USE_SAVED_COUNTS = os.getenv("USE_SAVED_COUNTS", "0") == "1"
active_output_excel = output_excel
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Path to your saved Chrome profile (already logged into NPTEL)
# This is inside your Downloads > SELFPACEDDUPLICATE > ChromeProfile folder
CHROME_PROFILE_PATH = os.path.join(
    os.path.expanduser("~"),
    "Downloads", "SELFPACEDDUPLICATE", "ChromeProfile"
)

# 1. Load the course list
try:
    if os.path.exists(input_excel):
        df = pd.read_excel(input_excel)
    elif os.path.exists(input_csv):
        df = pd.read_csv(input_csv)
    else:
        raise FileNotFoundError("courses.xlsx or courses.csv was not found")
except Exception as e:
    print(f"Error loading course list: {e}")
    exit()

if 'Course_URL' not in df.columns:
    print("Error: Excel file must contain a column named 'Course_URL'")
    exit()

df['Course_URL'] = df['Course_URL'].astype(str).str.strip()
df = df[df['Course_URL'].ne('') & df['Course_URL'].ne('nan')].copy()

if df.empty:
    print("Error: No course URLs found in the course list")
    exit()

def extract_course_id(url):
    parts = [part for part in urlparse(str(url)).path.split("/") if part]
    return parts[-1] if parts else ""

df['Course_ID'] = df['Course_URL'].apply(extract_course_id)

def save_output(dataframe):
    global active_output_excel

    try:
        dataframe.to_excel(active_output_excel, index=False)
    except PermissionError:
        active_output_excel = os.path.join(BASE_DIR, 'enrollment_data_updated.xlsx')
        dataframe.to_excel(active_output_excel, index=False)
        print(f"Excel file is open, so progress was saved to {active_output_excel}")

existing_results = {}
if USE_SAVED_COUNTS and os.path.exists(output_excel):
    try:
        old_df = pd.read_excel(output_excel)
        if 'Course_URL' in old_df.columns and 'Learners_Enrolled' in old_df.columns:
            for _, old_row in old_df.iterrows():
                old_url = str(old_row['Course_URL']).strip()
                old_count = old_row['Learners_Enrolled']
                if pd.notna(old_count) and str(old_count).strip().isdigit():
                    existing_results[old_url] = int(old_count)
    except Exception:
        existing_results = {}

# 2. Initialize WebDriver with saved Chrome profile (auto-login)
print("Starting browser with saved profile (auto-login)...")
options = Options()
options.add_argument(f"--user-data-dir={CHROME_PROFILE_PATH}")
options.add_argument("--profile-directory=Default")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.page_load_strategy = "eager"
options.add_experimental_option(
    "prefs",
    {
        "profile.managed_default_content_settings.images": 2,
        "profile.managed_default_content_settings.stylesheets": 2,
        "profile.managed_default_content_settings.fonts": 2,
    },
)

driver = webdriver.Chrome(options=options)

def page_needs_login():
    url = driver.current_url.lower()
    body = driver.find_element(By.TAG_NAME, "body").text.lower()
    return "signin" in url or "sign in to swayam" in body or "log in" in body

def wait_for_login_if_needed():
    if not page_needs_login():
        return True

    print("\nLogin required.")
    print("Please sign in in the Chrome window that opened.")
    print("After login, the script will continue automatically.")

    end_time = time.time() + 180
    while time.time() < end_time:
        time.sleep(3)
        if not page_needs_login():
            print("Login detected. Continuing...")
            return True

    print("Login was not completed within 3 minutes. Please run again after logging in.")
    return False

def extract_enrollment_count():
    body_text = driver.find_element(By.TAG_NAME, "body").text
    return extract_enrollment_count_from_text(body_text)

def html_to_text(html):
    html = re.sub(r"(?is)<script.*?</script>", " ", html)
    html = re.sub(r"(?is)<style.*?</style>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", html)
    return unescape(text)

def extract_enrollment_count_from_text(body_text):
    compact_text = re.sub(r"\s+", " ", body_text)

    patterns = [
        r"Learners enrolled\s*:?\s*([0-9,]+)",
        r"Students enrolled\s*:?\s*([0-9,]+)",
        r"Enrolled\s*:?\s*([0-9,]+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, compact_text, re.IGNORECASE)
        if match:
            return int(match.group(1).replace(",", ""))

    return None

def browser_cookies_from_driver():
    cookies = driver.get_cookies()
    return [
        {
            "name": cookie["name"],
            "value": cookie["value"],
            "domain": cookie.get("domain"),
            "path": cookie.get("path", "/"),
        }
        for cookie in cookies
    ]

def session_from_cookies(cookies):
    session = requests.Session()
    session.trust_env = False
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0 Safari/537.36"
            )
        }
    )

    for cookie in cookies:
        session.cookies.set(
            cookie["name"],
            cookie["value"],
            domain=cookie.get("domain"),
            path=cookie.get("path", "/"),
        )

    return session

def fetch_course_count(row_number, url, cookies):
    session = session_from_cookies(cookies)

    try:
        course_id = extract_course_id(url)
        if course_id:
            api_url = f"https://onlinecourses.nptel.ac.in/e-learning/api/coursepreview?course_id={course_id}"
            api_response = session.get(api_url, timeout=REQUEST_TIMEOUT, allow_redirects=True, verify=False)
            if api_response.ok:
                api_data = api_response.json()
                payload = api_data.get("payload", {})
                if isinstance(payload, str):
                    payload = json.loads(payload)

                student_count = payload.get("student_count")
                if student_count is not None:
                    return row_number, url, int(student_count), api_response.url, None

        response = session.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True, verify=False)
        text = html_to_text(response.text)
        lower_text = text.lower()
        lower_url = response.url.lower()

        if response.status_code == 404:
            return row_number, url, "Page Not Found / No Access", response.url, response.text

        if "signin" in lower_url or "sign in to swayam" in lower_text or "log in" in lower_text:
            return row_number, url, "Login Required", response.url, response.text

        count = extract_enrollment_count_from_text(text)
        if count is not None:
            return row_number, url, count, response.url, None

        return row_number, url, "Not Found / Error", response.url, response.text

    except Exception as e:
        return row_number, url, f"Error: {e}", url, None

def fetch_course_count_with_browser(row_number, url):
    try:
        driver.get(url)
        end_time = time.time() + REQUEST_TIMEOUT

        while time.time() < end_time:
            if page_needs_login():
                if not wait_for_login_if_needed():
                    return row_number, url, "Login Required"

            count = extract_enrollment_count()
            if count is not None:
                return row_number, url, count

            time.sleep(1)

        debug_file = os.path.join(debug_folder, f"debug_course_{row_number + 1}_browser.html")
        with open(debug_file, "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        return row_number, url, "Not Found / Error"

    except Exception as e:
        return row_number, url, f"Error: {e}"

# 3. Open NPTEL portal
driver.get("https://onlinecourses.nptel.ac.in/")
print("Waiting for NPTEL page to load...")
time.sleep(5)

if not wait_for_login_if_needed():
    driver.quit()
    exit()

enrolled_counts = []
results = {}
os.makedirs(debug_folder, exist_ok=True)

# 4. Scraping Phase
for index, row in df.iterrows():
    saved_count = existing_results.get(row['Course_URL'])
    if saved_count is not None:
        results[index] = saved_count

pending_rows = df[~df.index.isin(results.keys())]

if pending_rows.empty:
    print("\nAll courses already have saved enrollment counts.")
    df['Learners_Enrolled'] = [results.get(i, "") for i in df.index]
    save_output(df)
    driver.quit()
    exit()

print(f"\nStarting fast extraction for {len(pending_rows)} pending courses...")
if results:
    print(f"Resuming with {len(results)} already completed courses.")
browser_cookies = browser_cookies_from_driver()

with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
    futures = {
        executor.submit(fetch_course_count, index, row['Course_URL'], browser_cookies): index
        for index, row in pending_rows.iterrows()
    }

    completed = 0
    for future in as_completed(futures):
        index, url, count, final_url, debug_html = future.result()
        results[index] = count
        completed += 1

        if debug_html and completed <= 10:
            debug_file = os.path.join(debug_folder, f"debug_course_{index + 1}.html")
            with open(debug_file, "w", encoding="utf-8") as f:
                f.write(debug_html)

        if completed % 25 == 0 or completed == len(pending_rows):
            print(f"Progress: {completed}/{len(pending_rows)} pending courses checked")
            partial_df = df.copy()
            partial_df['Learners_Enrolled'] = [
                results.get(i, "Pending") for i in partial_df.index
            ]
            save_output(partial_df)

retry_statuses = {"Login Required", "Not Found / Error", "Page Not Found / No Access"}
retry_indexes = [
    index for index, count in results.items()
    if str(count).strip() in retry_statuses
]

if retry_indexes and BROWSER_RECHECK:
    print(f"\nRechecking {len(retry_indexes)} rows in Chrome...")
    for completed, index in enumerate(retry_indexes, start=1):
        url = df.loc[index, 'Course_URL']
        row_number, row_url, count = fetch_course_count_with_browser(index, url)
        results[row_number] = count
        print(f"Browser recheck: {completed}/{len(retry_indexes)}")

        partial_df = df.copy()
        partial_df['Learners_Enrolled'] = [
            results.get(i, "Pending") for i in partial_df.index
        ]
        save_output(partial_df)
elif retry_indexes:
    print(f"\nSkipped slow Chrome recheck for {len(retry_indexes)} rows.")
    print("To enable it, run this first: set BROWSER_RECHECK=1")

driver.quit()

enrolled_counts = [results.get(i, "Not Found / Error") for i in df.index]

# 5. Save Data
df['Learners_Enrolled'] = enrolled_counts
save_output(df)
print(f"\nDone! Data successfully saved to {active_output_excel}")

