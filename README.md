# HireFlow

HireFlow is a macOS desktop application for automating recruiter outreach for Data Analyst and Power BI Developer job searches. It imports recruiter contact lists, sends personalized bulk emails with resume and cover letter attachments, tracks replies over IMAP, and schedules follow-ups with delivery safeguards.

## Features

- CSV and Excel recruiter import with email validation and preview
- Gmail and Outlook compatible SMTP delivery
- HTML email composer with reusable templates and signature support
- Resume and cover letter PDF attachments
- SQLite-backed outreach history, follow-ups, recruiter status, and settings
- IMAP-based reply detection and recruiter reply marking
- APScheduler background reminders for follow-ups due after 3 days
- Duplicate prevention for initial outreach and max two follow-ups per recruiter
- Randomized send delays, retry logic, and daily send limits
- Modern PyQt6 macOS-style interface with light and dark themes
- Exportable delivery logs and live application log viewer

## Project Structure

```text
hireflow/
├── app/
├── assets/
├── config/
├── database/
├── logs/
├── samples/
├── services/
├── templates/
├── ui/
├── .env.example
├── build_macos.sh
├── main.py
├── README.md
└── requirements.txt
```

## Setup

1. Create and activate a Python 3.12+ virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Copy `.env.example` to `.env` and fill in your SMTP and IMAP details.
4. For Gmail, use an App Password instead of your normal account password.
5. Start the app:

```bash
python main.py
```

Recommended for local macOS development:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

Run the regression suite:

```bash
python -m unittest discover -s tests -v
```

## Using HireFlow

1. Open **Settings** and configure sender identity, SMTP, IMAP, rate limits, delays, and signature.
2. Use **Test SMTP** and **Test IMAP** to verify credentials.
3. Open **Recruiters** and load `samples/sample_recruiters.csv` or `samples/sample_recruiters.xlsx` to preview and import recruiter records.
4. Open **Send Emails**, attach your resume PDF and cover letter PDF, adjust the subject/body, and start the send queue.
5. Review upcoming reminders in **Follow-Ups**. HireFlow schedules the first follow-up 3 days after a successful initial send and allows a maximum of two follow-up attempts per recruiter.
6. Open **Logs** to review successful sends, failures, and application log output.

## Data Storage

- Development mode database: `database/hireflow.sqlite3`
- Development log file: `logs/hireflow.log`
- Packaged app runtime data:
  - `~/Library/Application Support/HireFlow/hireflow.sqlite3`
  - `~/Library/Logs/HireFlow/hireflow.log`

To clear recruiter/email runtime data while keeping saved settings:

```bash
python scripts/reset_runtime_state.py
```

## Sample Recruiter Files

- CSV: `samples/sample_recruiters.csv`
- Excel: `samples/sample_recruiters.xlsx`

## Anti-Spam and Safety Controls

- Randomized delay between emails using configurable min/max settings
- Retry logic with automatic SMTP reconnection
- Daily send limit
- Duplicate blocking for initial outreach
- Follow-up cap of two reminder emails per recruiter
- Password storage in macOS Keychain when saved through the app
- TLS certificate validation backed by `certifi` for reliable Gmail SMTP and IMAP connections in local venvs and packaged builds

## macOS Packaging

Install dependencies first, then build the `.app` bundle:

```bash
./build_macos.sh
```

Explicit build with a chosen interpreter:

```bash
PYTHON_BIN=./.venv/bin/python ./build_macos.sh
```

The build output will be placed in `dist/HireFlow.app`.

## Notes

- IMAP reply detection matches recruiter replies based on sender email address after the first outreach date.
- Gmail works with:
  - SMTP `smtp.gmail.com`, port `465`, security `ssl`
  - SMTP `smtp.gmail.com`, port `587`, security `starttls`
  - IMAP `imap.gmail.com`, port `993`, security `ssl`
- The default HTML templates support these placeholders:
  - `{{recruiter_name}}`
  - `{{company}}`
  - `{{sender_name}}`
  - `{{sender_email}}`
- Outlook users can configure `smtp.office365.com` and `outlook.office365.com` with `starttls` for SMTP and `ssl` for IMAP.
