# Gatherly Web

> A niche-interest offline activity discovery and community matching platform.

Gatherly Web, also known as **聚场**, is a Flask-based course project designed for people who want to discover local niche-interest activities and meet like-minded participants. The platform focuses on small communities such as film photography, city cycling, specialty coffee, independent publishing, music scenes, and other interest-based offline activities.

The project is currently developed as a classroom web development project using GitHub Issues, Labels, Milestones, Project Board, feature branches, and Pull Requests.

## Table of Contents

* [Project Overview](#project-overview)
* [Core Features](#core-features)
* [Current Development Scope](#current-development-scope)
* [Tech Stack](#tech-stack)
* [Project Structure](#project-structure)
* [Getting Started](#getting-started)
* [Main Routes](#main-routes)
* [Database Models](#database-models)
* [Development Workflow](#development-workflow)
* [Issue and Branch Convention](#issue-and-branch-convention)
* [Pull Request Checklist](#pull-request-checklist)
* [Team Roles](#team-roles)
* [Roadmap](#roadmap)
* [Screenshots](#screenshots)
* [Notes for Contributors](#notes-for-contributors)
* [License](#license)

## Project Overview

Gatherly Web solves a simple problem:

> People often want to join local niche-interest activities, but they do not know where to find reliable events or suitable companions.

The platform provides a lightweight event feed, activity details, user registration and login, activity registration, interest tags, community circles, posting features, rating mechanisms, and trust-related extensions.

This project intentionally avoids complex recommendation algorithms. Activities are expected to be organized around understandable rules such as time, location, interest tags, and trust signals.

## Core Features

### Implemented or in active development

* Home activity feed with card-based activity display
* Activity detail page
* User registration
* User login and logout
* Current login status display
* Activity publishing page
* Activity registration
* Duplicate registration prevention
* Full-capacity registration restriction
* Expired activity registration restriction
* Interest tag display and filtering
* Interest circle list
* Circle post foundation
* Activity rating and trust-score foundation
* Admin placeholder page
* Project documentation, meeting notes, issue rules, and style guide

### Planned or extended features

* User profile page
* Image upload for posts and comments
* Nested comments in interest circles
* Like and favorite toggle behavior
* Post and comment deletion
* Official circle management by administrators
* Official merchant verification
* Business license review flow
* Nearby users based on approximate IP region
* Direct messages between users
* Restriction on low-rated users creating activities
* Final screenshots, test report, and delivery documentation

## Current Development Scope

This repository is managed through GitHub Issues. Tasks are categorized by issue type and module.

Typical issue categories include:

* `type: user story` — user-facing feature requirement
* `type: task` — technical or implementation task
* `type: bug` — bug fix
* `type: docs` — documentation task
* `type: enhancement` — improvement or refinement

Typical module labels include:

* `module: activity`
* `module: auth`
* `module: circle`
* `module: frontend`
* `module: backend`
* `module: trust`
* `module: docs`

Milestones are used to organize the project into sprint-based delivery stages, such as:

* `Sprint 1 - Basic Framework`
* `Sprint 2 - Core Features`
* `Final Delivery - Gatherly Release`

## Tech Stack

This project intentionally uses a beginner-friendly and course-appropriate stack.

| Layer              | Technology                    |
| ------------------ | ----------------------------- |
| Backend            | Flask                         |
| Templates          | Jinja2                        |
| Database ORM       | Flask-SQLAlchemy              |
| Forms              | Flask-WTF, WTForms            |
| Database           | SQLite for local development  |
| Frontend           | HTML, CSS, Vanilla JavaScript |
| Styling            | Custom CSS                    |
| Package Management | `pip` + `requirements.txt`    |

The project does **not** use React, Vue, Bootstrap, PDM, or Poetry. Please do not introduce unrelated frameworks unless the team agrees and a new technical task is created.

## Project Structure

```text
gatherly-web/
├── app/
│   ├── __init__.py
│   ├── forms.py
│   ├── models.py
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── activity.py
│   │   ├── admin.py
│   │   ├── auth.py
│   │   ├── circle.py
│   │   └── profile.py
│   ├── static/
│   │   ├── css/
│   │   │   └── style.css
│   │   ├── images/
│   │   └── js/
│   │       └── main.js
│   └── templates/
├── docs/
│   ├── git-guide.md
│   ├── issue-rules.md
│   ├── meeting-notes.md
│   ├── project-plan.md
│   ├── product-backlog.md
│   ├── register-feature.md
│   ├── style-guide.md
│   ├── meeting-notes/
│   └── screenshots/
├── instance/
│   └── gatherly.db
├── scripts/
│   └── add_nickname_column.py
├── init_db.py
├── requirements.txt
├── run.py
└── README.md
```

`instance/gatherly.db` is a local development database file and should not be committed to Git.

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/Chesssley/gatherly-web.git
cd gatherly-web
```

### 2. Create a virtual environment

On Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\activate
```

On macOS or Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

Current dependencies include:

```text
Flask>=3.0
Flask-SQLAlchemy
Flask-WTF
Werkzeug
```

### 4. Initialize the database

```bash
python init_db.py
```

The local SQLite database will be generated under the Flask `instance/` directory.

### 5. Run the application

```bash
python run.py
```

Then open the application in your browser:

```text
http://127.0.0.1:5000
```

## Main Routes

| Route                     | Description            |
| ------------------------- | ---------------------- |
| `/`                       | Home activity feed     |
| `/activity/<id>`          | Activity detail page   |
| `/activity/<id>/register` | Activity registration  |
| `/activities/create`      | Activity creation page |
| `/login`                  | Login page             |
| `/register`               | Registration page      |
| `/logout`                 | Logout action          |
| `/circles`                | Interest circle list   |
| `/admin`                  | Admin placeholder page |

Route names may continue to change as features are implemented. Always check the latest `app/routes/` files before working on a related issue.

## Database Models

The main database models are defined in `app/models.py`.

Current or planned model areas include:

* `User`

  * username
  * nickname
  * email
  * password
  * avatar
  * interests
  * role
  * trust score
* `Activity`

  * title
  * description
  * location
  * start time
  * capacity
  * image
  * fee
  * status
  * preparation notes
  * organizer
* `Registration`

  * user
  * activity
  * registration status
  * registration time
* `Circle`

  * name
  * tag
  * description
  * posts
* `Post`

  * title
  * content
  * type
  * author
  * circle
* `Review`

  * activity
  * user
  * rating
  * comment
* `Rating`

  * organization score
  * venue score
  * experience score
  * average score
  * unique rating restriction per user and activity

Database fields should not be changed casually. If a new model field is needed, create or update a technical task first and explain the migration impact in the Pull Request.

## Development Workflow

This project follows an issue-first GitHub workflow.

### Standard workflow

```text
Read assigned Issue
→ Sync latest main
→ Create a feature branch
→ Modify only related files
→ Run local checks
→ Commit with a clear message
→ Push branch
→ Open Pull Request
→ Request review
→ Merge after approval
→ Delete merged branch
```

### Basic commands

```bash
git checkout main
git pull origin main

git checkout -b feat/us-04-02-create-activity-form

git status
git add .
git commit -m "feat(US-04-02): add activity title and description form"
git push --set-upstream origin feat/us-04-02-create-activity-form
```

Do not commit directly to `main`.

## Issue and Branch Convention

### Issue title format

Recommended examples:

```text
[US-01-01] Visitor can browse activity cards on the homepage
[TASK-02] Design core database models
[BUG-01] Fix login error message display
[DOC-04] Improve final README documentation
[UI-01] Define consistent Gatherly page style
```

### Branch naming

Use one branch per issue.

Recommended examples:

```text
feat/us-01-01-homepage-cards
feat/us-02-01-register
feat/us-04-02-create-activity-form
fix/bug-01-login-message
docs/doc-04-readme
ui/ui-01-style-guide
task/task-02-database-models
```

### Commit message format

Use concise and meaningful commit messages.

Recommended examples:

```text
feat(US-01-01): add homepage activity cards
feat(US-05-03): prevent duplicate activity registration
fix(BUG-01): correct login flash message
docs(DOC-04): update final README
style(UI-01): unify activity card layout
```

## Pull Request Checklist

Before opening a Pull Request, make sure:

* [ ] The branch is created from the latest `main`
* [ ] The PR solves only one Issue or a clearly related small group of Issues
* [ ] The modified files are within the allowed scope of the Issue
* [ ] The application can start locally with `python run.py`
* [ ] The related page or feature has been manually tested
* [ ] No temporary files, virtual environment files, cache files, or local databases are committed
* [ ] The PR description includes the related Issue number
* [ ] Screenshots are added for visible UI changes
* [ ] The Project Board status is moved to Code Review after the PR is opened

### PR template

```markdown
## Related Issue

Closes #XX

## Summary

- 
- 
- 

## Test Plan

- [ ] Ran `python run.py`
- [ ] Checked related page manually
- [ ] Confirmed no obvious UI or routing error
- [ ] Added screenshots if UI changed

## Modified Files

- 

## Review Focus

- 
```

## Team Roles

| Role                            | Main Responsibility                                                                   |
| ------------------------------- | ------------------------------------------------------------------------------------- |
| Project Lead / Scrum Master     | Planning, repository management, Issue management, PR review, sprint progress         |
| Homepage Frontend Owner         | Homepage activity feed, cards, interest tags, mobile layout                           |
| Activity Page Owner             | Activity detail page, activity creation page, activity information display            |
| User System Owner               | Registration, login, logout, login status, basic user data                            |
| Activity Business Logic Owner   | Registration, capacity limit, duplicate registration prevention, registration records |
| Community Owner                 | Interest circles, posts, comments, circle detail pages                                |
| Trust Mechanism Owner           | Rating, review, trust score, activity restrictions                                    |
| Documentation and Testing Owner | README, screenshots, meeting notes, test report, final delivery materials             |
| UI Style Owner                  | Shared CSS, card style, forms, buttons, mobile spacing                                |

## Roadmap

### Sprint 1 — Basic Framework

* [x] Flask project structure
* [x] Base templates and static resource structure
* [x] Homepage activity feed foundation
* [x] Activity detail page foundation
* [x] Registration and login foundation
* [x] Activity registration foundation
* [x] Interest tag filtering foundation
* [x] Interest circle list foundation
* [x] Basic documentation and collaboration rules

### Sprint 2 — Core Features

* [ ] Improve activity publishing workflow
* [ ] Complete activity rating and trust mechanism
* [ ] Restrict low-rated users from creating activities
* [ ] Add official merchant verification workflow
* [ ] Add official certification badge display
* [ ] Add nearby users feature based on approximate IP region
* [ ] Add direct messaging
* [ ] Restrict first message before mutual following
* [ ] Improve interest circle posts, comments, likes, favorites, and deletion behavior
* [ ] Unify frontend style for new features

### Final Delivery

* [ ] Complete final README
* [ ] Add screenshots
* [ ] Add test report
* [ ] Organize meeting notes
* [ ] Prepare demo materials
* [ ] Review all Issues, Labels, Milestones, and Project Board status
* [ ] Ensure `main` can run successfully before submission

## Screenshots

Screenshots should be stored in:

```text
docs/screenshots/
```

Recommended screenshot sections:

### Homepage Activity Feed

*Add screenshot here.*

### Activity Detail Page

*Add screenshot here.*

### Registration and Login

*Add screenshot here.*

### Activity Creation

*Add screenshot here.*

### Interest Circles

*Add screenshot here.*

### Rating and Trust Mechanism

*Add screenshot here.*

### Admin or Official Verification

*Add screenshot here.*

## Notes for Contributors

* Do not push directly to `main`
* Do not change database models without confirming the related Issue
* Do not introduce unrelated frameworks or dependencies
* Do not rewrite another member’s module without discussion
* Do not commit `.venv/`, `__pycache__/`, `.env`, local database files, or temporary screenshots
* Keep UI changes consistent with `docs/style-guide.md`
* Keep Issue numbers, Labels, Milestones, and Project Board status consistent
* Use one branch and one Pull Request for each Issue whenever possible

## Useful Documentation

* `docs/git-guide.md` — Git and GitHub collaboration guide
* `docs/issue-rules.md` — Issue naming, labels, milestones, and Project Board rules
* `docs/product-backlog.md` — Product backlog and feature planning
* `docs/project-plan.md` — Project planning notes
* `docs/style-guide.md` — Shared UI style guide
* `docs/meeting-notes.md` — Meeting notes
* `docs/screenshots/` — Project screenshots

## License

This repository is currently used as a course project. No open-source license has been specified yet.

Before reusing, distributing, or publishing this project outside the course context, please confirm the license and team agreement.
