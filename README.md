# Gatherly Web

Gatherly Web is a Flask web application for discovering local niche-interest activities and connecting with like-minded people through lightweight interest circles.

## Overview

Gatherly, also known as 聚场, focuses on offline activities that are often hard to find through mainstream event platforms: film camera walks, city cycling, pour-over coffee sessions, independent publishing meetups, board game socials, reading groups, and similar local communities.

The project is intentionally lightweight. It is not a complex algorithmic recommendation platform. It helps users discover activities through clear activity cards, city and location information, interest tags, simple search and filters, ratings, and trust signals.

This repository is maintained as a coursework and learning project using GitHub Issues, branches, Pull Requests, and documentation-driven delivery.

## Features

- Activity feed with cards, city/location information, activity images, tags, capacity, and click-through detail pages.
- Account registration, login, logout, email verification flows, profile editing, and account settings.
- Activity details with title, description, time, location, capacity, fee, preparation notes, comments, favorite state, and registration state.
- Activity creation for authenticated users, including title, description, time, location, capacity, fee, tags, circle link, preparation notes, timezone, and image upload.
- Activity registration with login checks, duplicate registration prevention, capacity checks, cancellation, and participant count display.
- Interest tag, date, city, and keyword discovery across activities, circles, and users.
- Interest circles with system circles, user-created circles, joining/leaving, access control, announcements, cover images, pinned posts, and circle activity links.
- Circle posts, post images, comments, threaded replies, comment images, and post/comment interactions.
- Rating and trust features, including activity reviews, participant reviews, trust score logs, and low-trust activity creation restrictions.
- User profiles, followers/following, nearby user discovery, notifications, and direct messages.
- Admin dashboard for users, activities, circles, posts, comments, merchant verification, and admin logs.

## Tech Stack

- Python
- Flask
- Flask-SQLAlchemy
- Flask-Migrate
- Flask-WTF
- Jinja2 templates
- HTML, CSS, and plain JavaScript
- SQLite by default through `sqlite:///gatherly.db`
- Neon PostgreSQL for the documented production database path through `DATABASE_URL`
- Cloudflare R2 for production uploads through the S3-compatible `boto3` client
- Render Web Service with `gunicorn wsgi:app`
- Werkzeug password utilities
- `python-dotenv` for environment variables

The project does not use React, Vue, Bootstrap, or a separate frontend build pipeline.

## Project Structure

```text
gatherly-web/
├── app/
│   ├── __init__.py
│   ├── models.py
│   ├── forms.py
│   ├── routes/
│   ├── services/
│   ├── static/
│   │   ├── css/
│   │   ├── js/
│   │   └── images/
│   ├── templates/
│   └── utils/
├── docs/
│   ├── README.md
│   ├── project-overview.md
│   ├── project-structure.md
│   ├── requirements.md
│   ├── product-backlog.md
│   ├── database-design.md
│   ├── er-diagram.md
│   ├── github-workflow.md
│   ├── issue-management.md
│   ├── development-guide.md
│   ├── style-guide.md
│   ├── test-report.md
│   ├── meeting-notes.md
│   ├── deployment-guide.md
│   ├── screenshots/
│   └── archive/
├── migrations/
├── scripts/
├── instance/
├── init_db.py
├── requirements.txt
├── run.py
├── seed_data.py
└── wsgi.py
```

See [docs/project-structure.md](docs/project-structure.md) for the detailed beginner-friendly structure guide.

## Getting Started

### 1. Clone the Repository

```bash
git clone https://github.com/Chesssley/gatherly-web.git
cd gatherly-web
```

### 2. Create a Virtual Environment

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\activate
```

macOS or Linux:

```bash
python -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Environment Setup

For local development, the app can run without a `.env` file because `app/__init__.py` provides development defaults.

Optional environment variables:

```text
SECRET_KEY=change-this-for-real-deployment
DATABASE_URL=sqlite:///gatherly.db
APP_ENV=development
```

If `DATABASE_URL` is not set, the app uses SQLite with `sqlite:///gatherly.db`, which Flask resolves under the `instance/` directory.

For the current production-style setup, use Render + Neon PostgreSQL + Cloudflare R2. See [docs/deployment-guide.md](docs/deployment-guide.md).

### 5. Initialize the Database

For a fresh local database:

```bash
python init_db.py
```

Optional sample data:

```bash
python seed_data.py
```

Database migrations are also present under `migrations/` for schema tracking.

### 6. Run the Application

```bash
python run.py
```

Then open:

```text
http://127.0.0.1:5000/
```

## Testing and Manual Verification

There is no dedicated automated test suite in the current repository. Use these checks before opening a Pull Request:

```bash
python -m compileall app
python -c "from app import create_app; app = create_app(); print('app loaded')"
python run.py
```

Manual feature checks should cover:

- Homepage activity feed loads.
- Register, login, and logout flows work.
- Activity detail pages open from activity cards.
- Authenticated users can create activities.
- Activity registration blocks anonymous, duplicate, full, or expired registration cases.
- Circle list, circle detail, post creation, comments, and interactions work.
- Rating, profile, direct message, notification, and admin pages match the expected permission rules.

See [docs/test-report.md](docs/test-report.md) for the current verification checklist.

## Documentation

- [Documentation Index](docs/README.md)
- [Project Overview](docs/project-overview.md)
- [Project Structure](docs/project-structure.md)
- [Requirements](docs/requirements.md)
- [Product Backlog](docs/product-backlog.md)
- [Database Design](docs/database-design.md)
- [ER Diagram](docs/er-diagram.md)
- [GitHub Workflow](docs/github-workflow.md)
- [Issue Management](docs/issue-management.md)
- [Development Guide](docs/development-guide.md)
- [Style Guide](docs/style-guide.md)
- [Test Report](docs/test-report.md)
- [Meeting Notes](docs/meeting-notes.md)
- [Deployment Guide](docs/deployment-guide.md)

## Team Workflow

- One issue, one branch, one pull request.
- Do not push directly to `main`.
- Keep GitHub Issues, Labels, Milestones, and the Project Board synchronized.
- Create a branch from the latest `main` before starting an issue.
- Keep each Pull Request focused on one issue or one clearly bounded documentation task.
- A Pull Request should be reviewed before merging.
- After merge, update local `main` before starting the next branch.

## Branch and Commit Convention

Recommended branch format:

```text
feat/us-04-01-create-activity-page
fix/bug-02-clean-test-circles
docs/doc-04-reorganize-docs-er
ui/ui-01-card-style
enh/enh-03-auto-dismiss-flash
```

Recommended commit format:

```text
type(ISSUE-ID): short description
```

Examples:

```text
feat(US-04-01): add activity creation page
fix(BUG-02): clean invalid test circles
docs(DOC-04): reorganize documentation and ER diagram
style(UI-01): align activity card spacing
```

## Roadmap

### Completed or Implemented in Current Code

- Flask application structure with blueprints.
- Account registration, login, logout, account settings, and email verification helpers.
- Homepage activity feed, activity search, activity detail, activity creation, registration, cancellation, comments, favorites, and reviews.
- Interest circles, circle creation, membership, access requests, announcements, cover images, posts, images, comments, replies, and interactions.
- Profiles, personal content sections, followers/following, nearby users, notifications, and direct messages.
- Admin dashboard for users, activities, circles, posts, comments, merchant verification, and logs.
- SQLite default database with SQLAlchemy models and migration support.

### In Progress or Delivery-Focused

- Final documentation cleanup.
- Final manual test report.
- Final screenshots and demo material collection.
- GitHub Issue, Label, Milestone, and Project Board synchronization.

### Future Improvements

- Add automated tests for route permissions and core business rules.
- Replace development schema compatibility helpers with a stricter migration-only workflow.
- Maintain the documented [Render + Neon + Cloudflare R2 deployment guide](docs/deployment-guide.md) as the production path evolves.
- Add richer search and recommendation rules while keeping the product understandable.
- Expand screenshot coverage for final presentation and course reports.

## Contributing

1. Pick or create a GitHub Issue.
2. Create a focused branch for that Issue.
3. Make a small, reviewable change.
4. Run the basic checks and manually verify the affected pages.
5. Open a Pull Request and link the Issue.
6. Wait for review before merging.

## License / Course Notice

This project is developed for coursework and learning purposes. No separate open-source license is currently provided.
