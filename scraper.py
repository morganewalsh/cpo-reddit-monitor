"""
BU Reddit Safety Monitor — Local Script
----------------------------------------
Runs on your computer and writes safety-related posts
from r/BostonUniversity directly to a shared Google Sheet.

FIRST RUN:
    A browser window will open asking you to log in to Google.
    Do this once and you'll never need to do it again.

HOW TO RUN MANUALLY:
    Open Command Prompt in this folder and run:
    python scraper.py

HOW IT RUNS AUTOMATICALLY:
    Windows Task Scheduler runs this every morning at 9am.
    See SETUP_GUIDE.md for instructions.
"""

import os
import requests
import time
import gspread
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from datetime import datetime, timezone

# ----------------------------------------------------------------
# SETTINGS — edit these if needed
# ----------------------------------------------------------------

SUBREDDIT       = "BostonU"
PAGES_TO_SCRAPE = 5    # How many pages of Reddit to check
MIN_UPVOTES     = 10   # Minimum upvotes to include a post
DELAY           = 3    # Seconds to wait between page requests

# Name of your Google Sheet (must match exactly)
SHEET_NAME = "CPO Reddit Key Posts"

# These files will be created in the same folder as this script.
# credentials.json — downloaded from Google Cloud Console (one time)
# token.json       — saved automatically after your first login (one time)
CREDENTIALS_FILE = "credentials.json"
TOKEN_FILE       = "token.json"

# Posts must match at least one of these to be included
SAFETY_KEYWORDS = [
    "safety", "crime", "theft", "stolen", "robbery", "assault",
    "attack", "arrested", "police", "bupd", "emergency", "alert",
    "suspicious", "threat", "violence", "shooting", "stabbing",
    "break-in", "break in", "trespassing", "harassment",
    "fire alarm", "evacuation", "lockdown", "power outage",
    "elevator", "hazard", "flood", "leak", "construction",
    "warren towers", "west campus", "bay state", "shelton",
    "myles", "stuvi", "brownstone", "CGS", "COM", "CAS",
    "questrom", "agganis", "fitrec", "GSU", "marsh chapel",
    "student village", "south campus", "fenway", "comm ave", "BUPD",
    "data science", "cds", "help"
]

# Posts matching any of these will be excluded
EXCLUDE_KEYWORDS = [
     "Zara Larson", "transfer", "Zara", "Ticket"
]

# ----------------------------------------------------------------
# GOOGLE SHEETS AUTH
# The scopes tell Google what permissions the script needs.
# ----------------------------------------------------------------

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# ----------------------------------------------------------------
# STEP 1: Connect to Google Sheets
# ----------------------------------------------------------------

def connect_to_sheets():
    """
    Logs in to Google Sheets using OAuth.

    First run: opens a browser window so you can log in.
    Every run after: uses the saved token.json automatically.
    """
    print("Connecting to Google Sheets...")
    creds = None

    # If we've logged in before, load the saved token
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    # If no token exists, or it's expired, do the browser login
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            # Token expired — refresh it silently (no browser needed)
            creds.refresh(Request())
        else:
            # First time — open browser for login
            print("  Opening browser for one-time Google login...")
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        # Save the token so we don't need to log in again
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
        print("  Login saved — you won't need to do this again.")

    client = gspread.authorize(creds)
    print("  Connected!")
    return client

# ----------------------------------------------------------------
# STEP 2: Get or create the Posts worksheet
# ----------------------------------------------------------------

def get_worksheet(client):
    sheet = client.open(SHEET_NAME)
    try:
        worksheet = sheet.worksheet("Posts")
    except gspread.WorksheetNotFound:
        worksheet = sheet.add_worksheet(title="Posts", rows=1000, cols=10)
        worksheet.append_row([
            "Date Added", "Date Posted", "Title", "Author",
            "Upvotes", "Comments", "URL", "Matched Keywords"
        ])
        print("  Created Posts tab with headers.")
    return worksheet

# ----------------------------------------------------------------
# STEP 3: Scrape Reddit from your local machine
# ----------------------------------------------------------------

def scrape_reddit():
    print(f"\nScraping r/{SUBREDDIT}...")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json"
    }

    all_posts = []
    after = ""

    for page in range(PAGES_TO_SCRAPE):
        url = f"https://old.reddit.com/r/{SUBREDDIT}/hot.json?limit=25"
        if after:
            url += f"&after={after}"

        print(f"  Fetching page {page + 1} of {PAGES_TO_SCRAPE}...")

        try:
            response = requests.get(url, headers=headers, timeout=10)

            if response.status_code != 200:
                print(f"  Warning: Reddit returned status {response.status_code}. Stopping.")
                break

            data  = response.json()
            posts = data.get("data", {}).get("children", [])

            if not posts:
                print("  No more posts found.")
                break

            for post in posts:
                p = post.get("data", {})
                all_posts.append({
                    "title":       p.get("title", ""),
                    "author":      p.get("author", "[deleted]"),
                    "upvotes":     p.get("ups", 0),
                    "numComments": p.get("num_comments", 0),
                    "createdUtc":  p.get("created_utc", 0),
                    "url":         "https://reddit.com" + p.get("permalink", ""),
                })

            after = data.get("data", {}).get("after", "")
            if not after:
                break

            time.sleep(DELAY)

        except Exception as e:
            print(f"  Error on page {page + 1}: {e}")
            break

    print(f"  Found {len(all_posts)} total posts.")
    return all_posts

# ----------------------------------------------------------------
# STEP 4: Filter posts by keywords and upvotes
# ----------------------------------------------------------------

def filter_posts(posts):
    filtered = []
    for post in posts:
        title_lower = post["title"].lower()

        if post["upvotes"] < MIN_UPVOTES:
            continue

        matches_safety = any(kw.lower() in title_lower for kw in SAFETY_KEYWORDS)
        if not matches_safety:
            continue

        matches_exclude = any(kw.lower() in title_lower for kw in EXCLUDE_KEYWORDS)
        if matches_exclude:
            continue

        matched = [kw for kw in SAFETY_KEYWORDS if kw.lower() in title_lower]
        post["matchedKeywords"] = ", ".join(matched[:5])
        filtered.append(post)

    print(f"  {len(filtered)} posts passed the safety filter.")
    return filtered

# ----------------------------------------------------------------
# STEP 5: Avoid duplicates
# ----------------------------------------------------------------

def get_existing_urls(worksheet):
    try:
        existing = worksheet.col_values(7)
        return set(existing)
    except Exception:
        return set()

# ----------------------------------------------------------------
# STEP 6: Write new posts to the sheet
# ----------------------------------------------------------------

def append_to_sheet(worksheet, posts, existing_urls):
    added = 0
    for post in posts:
        if post["url"] in existing_urls:
            continue

        post_date = datetime.fromtimestamp(
            post["createdUtc"], tz=timezone.utc
        ).strftime("%Y-%m-%d") if post["createdUtc"] else "unknown"

        today = datetime.now().strftime("%Y-%m-%d")

        worksheet.append_row([
            today,
            post_date,
            post["title"],
            post["author"],
            post["upvotes"],
            post["numComments"],
            post["url"],
            post.get("matchedKeywords", "")
        ])
        added += 1

    print(f"  {added} new posts added to the sheet.")
    return added

# ----------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------

def main():
    print("=" * 40)
    print("BU Reddit Safety Monitor")
    print(f"Run time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 40)

    client    = connect_to_sheets()
    worksheet = get_worksheet(client)

    all_posts      = scrape_reddit()
    filtered_posts = filter_posts(all_posts)
    existing_urls  = get_existing_urls(worksheet)

    added = append_to_sheet(worksheet, filtered_posts, existing_urls)

    print(f"\nDone! {added} new posts added to '{SHEET_NAME}'.")

if __name__ == "__main__":
    main()
