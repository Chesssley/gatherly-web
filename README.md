# Gatherly Web

Gatherly Web is a Flask web application for discovering local interest-based activities and connecting with people through lightweight interest circles.

The current production architecture is Render + Neon PostgreSQL + Cloudflare R2 + GitHub. Render runs the web service, Neon stores relational application data, Cloudflare R2 stores uploaded media files, and GitHub stores source code, documentation, templates, static assets, and database migrations.

## Project Overview

Gatherly focuses on offline activities that are often hard to find on mainstream event platforms: film camera walks, city cycling, pour-over coffee sessions, independent publishing meetups, board game socials, reading groups, music meetups, and similar local communities.

The project is intentionally lightweight. It helps users discover activities through activity cards, city and location information, tags, search and filters, ratings, trust signals, interest circles, comments, notifications, and direct messages.

## Features

- Activity feed, search, filters, detail pages, creation, registration, cancellation, favorites, comments, and reviews.
- User registration, login, logout, email verification, account settings, profile editing, followers, nearby discovery, notifications, and direct messages.
- Interest circles with system circles, user-created circles, joining/leaving, announcements, cover images, pinned posts, posts, images, comments, replies, and interactions.
- Ratings and trust features through legacy `Review`, `ActivityReview`, `UserReview`, and `TrustScoreLog`.
- Admin dashboard for users, activities, circles, posts, comments, merchant verification, and admin logs.
- Cloudflare R2-backed image uploads with local fallback only for development when R2 is not configured.

## Tech Stack

- Python
- Flask
- Jinja2
- HTML / CSS / JavaScript
- Flask-SQLAlchemy
- Flask-Migrate / Alembic
- PostgreSQL on Neon
- Cloudflare R2 for object storage
- Render for deployment
- GitHub for version control
- Flask-WTF
- Werkzeug password utilities
- `boto3` for the R2 S3-compatible API
- `python-dotenv` for local environment variables
- `gunicorn` / `wsgi.py` for production startup

The project does not use React, Vue, Bootstrap, or a separate frontend build pipeline.

## Architecture

| Layer | Service | Responsibility |
|---|---|---|
| Web runtime | Render Web Service | Pulls code from GitHub, installs dependencies, and runs `gunicorn wsgi:app`. |
| Database | Neon PostgreSQL | Stores relational application data and media URLs/object keys. |
| Object storage | Cloudflare R2 | Stores uploaded media files such as avatars, activity images, post images, comment images, message images, circle covers, and merchant verification documents. |
| Version control | GitHub | Stores source code, templates, CSS, JavaScript, README, docs, scripts, and Alembic migrations. |
| Database migration | Flask-Migrate / Alembic | Tracks schema changes in `migrations/` and applies them with `flask db upgrade`. |

Render is not persistent storage. Uploaded files must go to Cloudflare R2, and user data must go to Neon PostgreSQL.

## Data Storage Policy

User accounts, posts, comments, activities, registrations, ratings, private messages, notifications, admin logs, merchant verification records, email verification records, and image URLs are stored in Neon PostgreSQL.

Uploaded media files are stored in Cloudflare R2. The database stores media URLs or object keys only. It does not store image file bodies.

SQLite is only a local development fallback if `DATABASE_URL` is not set. It is not the production database. Local uploads under `app/static/uploads/` are also only a local development fallback or legacy migration source, not production storage.

GitHub must not contain real user data, real uploaded images, database passwords, R2 secrets, `.env`, database backups, or image backups. Render Environment stores deployment secrets and runtime configuration.

## Environment Variables

Use placeholders only in documentation and examples. Do not commit real values.

```text
DATABASE_URL=<neon-postgresql-url>
SECRET_KEY=<strong-secret-key>
R2_ACCOUNT_ID=<cloudflare-account-id>
R2_ACCESS_KEY_ID=<r2-access-key-id>
R2_SECRET_ACCESS_KEY=<r2-secret-access-key>
R2_BUCKET_NAME=gatherly-uploads
R2_PUBLIC_BASE_URL=<https://public-r2-base-url>
ADMIN_USERNAME=<admin-username>
ADMIN_EMAIL=<admin-email>
ADMIN_PASSWORD=<admin-password>
BREVO_API_KEY=<brevo-api-key-if-email-provider-is-brevo>
```

Additional email variables used by the current code may include `EMAIL_PROVIDER`, `BREVO_SENDER_EMAIL`, `BREVO_SENDER_NAME`, `EMAIL_API_TIMEOUT`, or SMTP variables. See [docs/deployment-guide.md](docs/deployment-guide.md).

Render should use the Neon pooled connection URL for normal runtime database connections. Local migration and maintenance work should use the Neon direct connection URL, not the pooler URL.

## Database Migration

Do not rely on `db.create_all()` for production schema changes. Production schema changes must use Flask-Migrate / Alembic migrations.

For model changes:

```powershell
$env:FLASK_APP='wsgi:app'
$env:DATABASE_URL='<Neon Direct URL, not the pooler URL>'
flask db migrate -m "describe schema change"
flask db upgrade
```

Commit both the model change and the generated files under `migrations/`. Database field changes should be reviewed in their own Pull Request when possible.

## Deployment

Production entry point: Render Web Service.

Standard deployment flow:

1. Create a local branch from the latest `main`.
2. Make changes and commit them locally.
3. Push the branch to GitHub.
4. Open a GitHub Pull Request.
5. Review and merge into `main`.
6. Render automatically deploys from `main`.

Ordinary code and documentation changes do not require manual Neon or R2 changes. Database schema changes require Alembic migrations and `flask db upgrade` against Neon. Image upload logic changes go through GitHub, secrets stay in Render Environment, uploaded files go to R2, and Neon stores only URLs/object keys.

## Project Structure

```text
gatherly-web/
|-- app/
|   |-- __init__.py
|   |-- models.py
|   |-- routes/
|   |-- services/
|   |   `-- storage.py
|   |-- static/
|   |-- templates/
|   `-- utils/
|-- docs/
|-- migrations/
|-- scripts/
|-- instance/
|-- init_db.py
|-- requirements.txt
|-- run.py
`-- wsgi.py
```

See [docs/project-structure.md](docs/project-structure.md) for the full current repository structure.

## Local Development

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

Open `http://127.0.0.1:5000/`.

If `DATABASE_URL` is not set, the app falls back to `sqlite:///gatherly.db` under Flask's instance directory. This is only for local quick development. For migration work, set `DATABASE_URL` to a Neon direct URL.

## Verification

Basic checks before opening a Pull Request:

```powershell
python -m compileall app
python -c "from app import create_app; app = create_app(); print('app loaded')"
```

Manual checks should cover the affected pages and workflows. See [docs/test-report.md](docs/test-report.md).

## Documentation Links

- [Documentation Index](docs/README.md)
- [Project Overview](docs/project-overview.md)
- [Project Structure](docs/project-structure.md)
- [Database Design](docs/database-design.md)
- [ER Diagram](docs/er-diagram.md)
- [Deployment Guide](docs/deployment-guide.md)
- [Maintenance Guide](docs/maintenance-guide.md)
- [Development Guide](docs/development-guide.md)
- [GitHub Workflow](docs/github-workflow.md)
- [Issue Management](docs/issue-management.md)
- [Test Report](docs/test-report.md)

## Team Workflow

- One issue, one branch, one Pull Request.
- Do not push directly to `main`.
- Keep each Pull Request focused.
- Run the relevant checks before opening a Pull Request.
- Use PR review before merge.
- Merge to `main` only after review.
- Let Render deploy from `main`.

Recommended commit format:

```text
type(ISSUE-ID): short description
```

Example:

```text
docs(DOC-06): update documentation for Render Neon R2 architecture
```

## Security Rules

Do not commit `.env`, `DATABASE_URL`, `SECRET_KEY`, `R2_SECRET_ACCESS_KEY`, `ADMIN_PASSWORD`, real database backups, or real uploaded image backups.

If a secret is exposed, rotate it at the provider, update Render Environment, and check Neon, R2, Render, and GitHub activity.

## License / Course Notice

This project is developed for coursework and learning purposes. No separate open-source license is currently provided.
