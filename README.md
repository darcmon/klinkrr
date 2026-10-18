# klinkrr

Permanent, human-readable links to files and redirects that you can update without changing the URL. Admins submit a new version of a location such as `/employee-handbook`, it's approved (or published immediately, depending on the location's setting), and the same link serves the new content.

This README describes the current app. See [architecture direction](docs/architecture.md) for agreed plans around organization and personal namespaces, multi-organization permissions, and integrations.

## Prerequisites

- Python 3.11+
- Node.js 20+ and npm
- Docker with Docker Compose

## Setup

Once you've done the one-time setup below, `make up` starts the database/storage and `make dev` runs backend + frontend together in one terminal (Ctrl-C stops both). Run `make install` after cloning to create the venv and install frontend deps.

### 1. Environment

```bash
cp .env.example .env
```

Set the first admin's login in `.env`:

```dotenv
ADMIN_EMAIL=you@example.com
ADMIN_PASSWORD=choose-a-password
```

These are only used to create the first owner when the database has no users. The other defaults work for local development.

### 2. Database and file storage

```bash
docker compose up -d
```

This starts PostgreSQL on `localhost:5432` and MinIO (S3-compatible storage) on `localhost:9000`.

Create the storage bucket: open the MinIO console at http://localhost:9001, sign in with `minioadmin` / `minioadmin`, and create a bucket named after `S3_BUCKET` in `.env` (`file-approval` by default).

### 3. Backend

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
alembic upgrade head
uvicorn backend.main:app --reload --port 8000
```

On first start this creates the owner from `ADMIN_EMAIL` and `ADMIN_PASSWORD`. Check with http://localhost:8000/health.

### 4. Frontend

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 and sign in with the admin email and password.

## Optional

### Microsoft and Google sign-in

Register an OAuth app with each provider using these redirect URLs:

```text
http://localhost:8000/admin/auth/microsoft/callback
http://localhost:8000/admin/auth/google/callback
```

Then set `MICROSOFT_CLIENT_ID`, `MICROSOFT_CLIENT_SECRET`, `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` in `.env` and restart the backend.

Only people already added as members can sign in (**Settings → Members**). The first time they use Microsoft or Google with that email, it links to their account.

### Redirect links

Submitting redirect links runs a URL safety check through Google Web Risk. Set `WEB_RISK_API_KEY` in `.env`; without it, link submissions are refused. File uploads work without it.

## Tests

```bash
pytest                      # backend
cd frontend && npm test     # frontend
```

Tests that need a real database are skipped unless `PHASE1_TEST_DATABASE_URL` points at a disposable, migrated PostgreSQL database. They create and delete data, so never point it at a database you care about.

## Local data

Treat everything in the local database and MinIO as disposable. `docker compose down -v` deletes both.

## Deploying

`render.yaml` is a Render Blueprint for the API, admin app, database and a daily audit-log cleanup job. Set `ENVIRONMENT=production` in any deployment: the API then refuses to start with unsafe settings such as a placeholder `SECRET_KEY` or non-https origins, and lists what to fix.
