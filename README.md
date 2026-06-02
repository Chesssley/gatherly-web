# Gatherly Web

A Flask-based local niche-interest activity discovery and community matching platform.

## Overview

Gatherly Web helps people discover local niche-interest activities and meet like-minded participants in a lightweight community setting. It is designed around practical offline scenarios: browsing nearby or themed activities, joining interest circles, registering for events, posting in communities, messaging other users, and using ratings and trust signals to support safer participation.

The project is developed as a course team web project with GitHub Issues, Labels, Milestones, Project Board tracking, feature branches, and Pull Requests.

## Features

### Account & Authentication

- User registration, login, logout, and account deletion.
- Username or email login.
- Password hashing with Werkzeug.
- Login failure rate limiting.
- Profile editing, avatar upload, interests, city, bio, and visibility settings.

### Email Verification

- Email verification code flow for registration.
- Verification for email changes, password changes, and password reset.
- Console email provider for local development.
- Brevo Transactional Email API and SMTP fallback support.

### Activity Discovery

- Homepage activity feed with category, date, city, and keyword search.
- Search suggestions across activities, circles, and users.
- Activity detail pages with organizer, time, location, capacity, fee, tags, attendee preview, comments, and participation state.
- Activity favorites.

### Activity Creation

- Authenticated users can publish activities.
- Activity fields include title, description, detail, city, location, start/end time, timezone, capacity, fee, tags, circle link, preparation notes, and image.
- Low-trust users are blocked from creating activities.
- Verified merchants and admins can mark official or featured activities.
- Organizers and admins can close or cancel activities.

### Registration / Participation

- Activity registration with duplicate registration prevention.
- Capacity and expired-activity checks.
- Registration cancellation before the activity starts.
- Organizer registration is created automatically for newly published activities.

### Interest Circles

- System and user-created interest circles.
- Circle joining, leaving, private access requests, owner transfer, moderator role management, announcements, covers, and pinned posts.
- Circle activity links and member counts.

### Posts / Comments / Replies

- Circle posts with optional images.
- Post comments, threaded replies, and optional comment images.
- Activity comments.
- Like, favorite, and share interaction records for posts and comments.
- Soft deletion and moderation statuses for posts and comments.

### Messaging

- Direct messages between users.
- Text and image messages.
- Conversation polling API.
- Hide/delete conversation state per user.
- Message retention cleanup.
- First-message restriction before mutual follow or reply.

### User Profile & Account Settings

- Public and private profile views.
- Personal pages for created activities, joined activities, circles, posts, comments, and interactions.
- User search, followers, following, follow/unfollow, and nearby users based on coarse location signals.
- Merchant verification application from account settings.

### Rating & Trust

- Activity reviews with multi-dimensional scores.
- Participant-to-participant reviews after activities end.
- User trust score recalculation from received participant reviews.
- Trust score change logs.
- Legacy `Review` model kept for compatibility with older activity flows.

### Admin Dashboard

- Admin dashboard with statistics and recent operation logs.
- User management, ban/unban, promote/demote admin, and merchant qualification management.
- Activity status and featured status management.
- Circle, post, and comment moderation.
- Merchant verification review.
- Admin account settings with email/password verification.

### Responsive UI

- Jinja2 templates with custom CSS and vanilla JavaScript.
- Responsive layouts for activity feed, detail pages, circles, profiles, messages, and admin pages.

## Tech Stack

| Area | Technology |
| --- | --- |
| Backend | Flask |
| ORM | Flask-SQLAlchemy |
| Forms / validation | Flask-WTF, WTForms, email-validator |
| Password security | Werkzeug |
| Frontend | Jinja2 templates, HTML, CSS, vanilla JavaScript |
| Database | SQLite via SQLAlchemy |
| Email service | Console provider, Brevo Transactional Email API, SMTP |
| Deployment | Standard Flask app; documented for PythonAnywhere-style hosting |
| Package management | `pip` and `requirements.txt` |

## Repository Structure

```text
gatherly-web/
├── app/
│   ├── __init__.py              # Flask app factory and blueprint registration
│   ├── forms.py                 # WTForms definitions
│   ├── models.py                # SQLAlchemy models and SQLite schema helpers
│   ├── routes/                  # Flask blueprints by feature area
│   ├── static/                  # CSS, JavaScript, images, and upload placeholders
│   ├── templates/               # Jinja2 templates
│   └── utils/                   # Email, upload, and location helpers
├── docs/                        # Project documentation in Chinese
│   ├── archive/                 # Historical documents kept for reference
│   ├── screenshots/             # Screenshots and delivery evidence
│   ├── database-design.md
│   ├── development-workflow.md
│   ├── er-diagram.mmd
│   ├── feature-guide.md
│   ├── project-overview.md
│   ├── project-structure.md
│   ├── setup-and-deployment.md
│   └── testing-guide.md
├── scripts/                     # Maintenance scripts
├── init_db.py                   # Local database initialization and demo seed setup
├── seed_data.py                 # Demo activity data
├── requirements.txt             # Python dependencies
├── run.py                       # Local Flask entry point
└── README.md
```

The local SQLite database is created under `instance/` as `gatherly.db`. Runtime files such as `instance/`, `.env`, virtual environments, `__pycache__/`, local database files, and user uploads are managed by `.gitignore` and should not be committed.

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/Chesssley/gatherly-web.git
cd gatherly-web
```

### 2. Create a virtual environment

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

macOS / Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

For local development, the app can run without custom variables because it falls back to a development secret key and console email provider. For realistic testing, set at least `SECRET_KEY` and the email provider variables you need.

Windows PowerShell example:

```powershell
$env:SECRET_KEY = "replace-with-a-local-development-secret"
$env:EMAIL_PROVIDER = "console"
```

macOS / Linux example:

```bash
export SECRET_KEY="replace-with-a-local-development-secret"
export EMAIL_PROVIDER="console"
```

### 5. Initialize the database

```bash
python init_db.py
```

To create or update an admin account during initialization, set all three variables before running the command: `ADMIN_USERNAME`, `ADMIN_EMAIL`, and `ADMIN_PASSWORD`.

### 6. Run locally

```bash
python run.py
```

Open:

```text
http://127.0.0.1:5000
```

## Environment Variables

Only variables read by the current codebase are listed here.

| Variable | Purpose |
| --- | --- |
| `SECRET_KEY` | Flask secret key and email-code hash secret. Defaults to `dev-secret-key` if unset. |
| `APP_ENV` | Marks production mode when set to `production` or `prod`. |
| `FLASK_ENV` | Also checked for production mode. |
| `ENV` | Also checked for production mode. |
| `SESSION_COOKIE_SECURE` | Explicitly enables secure session cookies when set to `1`, `true`, `yes`, or `on`. |
| `EMAIL_PROVIDER` | Email provider: `console`, `brevo`, or `smtp`. Defaults to `console`. |
| `EMAIL_API_TIMEOUT` | Timeout in seconds for Brevo API requests. Defaults to `15`. |
| `BREVO_API_KEY` | Brevo Transactional Email API key. |
| `BREVO_SENDER_EMAIL` | Verified Brevo sender email. |
| `BREVO_SENDER_NAME` | Brevo sender display name. Defaults to `Gatherly`. |
| `MAIL_SERVER` | SMTP server host. |
| `MAIL_PORT` | SMTP server port. Defaults to `587`. |
| `MAIL_USERNAME` | SMTP username. |
| `MAIL_PASSWORD` | SMTP password. |
| `MAIL_USE_TLS` | Enables SMTP TLS when set to `1`, `true`, `yes`, or `on`. |
| `MAIL_DEFAULT_SENDER` | SMTP sender address. |
| `ADMIN_USERNAME` | Optional admin username used by `init_db.py`. |
| `ADMIN_EMAIL` | Optional admin email used by `init_db.py`. |
| `ADMIN_PASSWORD` | Optional admin password used by `init_db.py`. |

Example local configuration:

```text
SECRET_KEY=replace-with-a-long-random-secret
EMAIL_PROVIDER=console
```

Never commit real secrets, passwords, API keys, `.env` files, or local database files.

## Database

Gatherly Web uses SQLite for local development with SQLAlchemy models defined in `app/models.py`. The app factory also runs schema compatibility helpers for SQLite so older local databases can be brought forward during development.

- Database design: [docs/database-design.md](docs/database-design.md)
- Mermaid ER source: [docs/er-diagram.mmd](docs/er-diagram.mmd)

## Documentation

The detailed project documentation is maintained in Chinese:

- [Project overview](docs/project-overview.md): positioning, users, goals, and current scope.
- [Feature guide](docs/feature-guide.md): implemented modules and remaining improvements.
- [Project structure](docs/project-structure.md): current repository layout and directory responsibilities.
- [Database design](docs/database-design.md): models, fields, relationships, constraints, and ER diagram notes.
- [Setup and deployment](docs/setup-and-deployment.md): local setup, environment variables, database initialization, and PythonAnywhere-style deployment notes.
- [Development workflow](docs/development-workflow.md): GitHub Issues, branches, commits, Pull Requests, labels, milestones, and Project Board rules.
- [Testing guide](docs/testing-guide.md): executable checks and manual acceptance checklist.
- [Archive](docs/archive/): historical documents retained for reference.

## GitHub Workflow

This project follows issue-driven development:

1. Create or confirm a GitHub Issue.
2. Create one branch for the Issue from the latest `main`.
3. Implement only the related change.
4. Run local checks.
5. Commit with a clear message.
6. Push the branch.
7. Open a Pull Request and link the Issue.
8. Review before merge.

Do not push directly to `main`.

Branch examples:

```text
feat/us-04-02-create-activity-form
fix/bug-01-login-message
docs/doc-04-readme
ui/ui-01-style-guide
task/task-02-database-models
```

Commit examples:

```text
feat(US-04-02): add activity creation validation
fix(BUG-01): correct login error handling
docs(DOC-04): reorganize project documentation
```

## Testing

The repository currently does not include a dedicated automated test suite. At minimum, run the Python syntax check:

```bash
python -m compileall app run.py
```

For feature work, also start the app with `python run.py` and manually verify the affected pages and routes. See [docs/testing-guide.md](docs/testing-guide.md) for the current checklist.

## Deployment

The codebase is a standard Flask application exposed as `app` in `run.py`. It can be deployed on PythonAnywhere-style Flask hosting by creating a virtual environment, installing `requirements.txt`, setting environment variables on the host, initializing the SQLite database, and pointing the WSGI entry to the Flask app.

For production-like deployment:

- Set a strong `SECRET_KEY`.
- Use HTTPS.
- Set `APP_ENV=production` or `SESSION_COOKIE_SECURE=true`.
- Prefer the Brevo email provider when outbound SMTP is not available.
- Do not upload local `instance/gatherly.db`, `.env`, or development cache files to Git.

More details are in [docs/setup-and-deployment.md](docs/setup-and-deployment.md).

## Roadmap

Current improvement areas are based on the implemented code and the project workflow:

- Add automated tests for authentication, activity registration, messaging, and admin moderation.
- Improve migration handling beyond the current SQLite compatibility helpers.
- Expand validation and error handling around uploaded images and moderation flows.
- Improve UI consistency after feature additions.
- Add clearer seed data and demo account documentation.
- Review privacy behavior for nearby users and message retention before production use.

## Team / Course Context

Gatherly Web is maintained as a course team web development project. The repository demonstrates practical Flask development, GitHub collaboration, database modeling, issue-driven planning, and iterative delivery without exposing private course or team information.

## License

No license has been specified yet.
