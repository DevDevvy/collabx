# collabx

A tiny “Burp Collaborator-like” HTTP collector + CLI.

- **Collector** (FastAPI): receives GET/POST callbacks and logs them.
- **CLI**: runs locally **or** deploys to **GCP Cloud Run** (first provider), then tails logs via polling (default) or opt-in SSE.

Polling is the default (every **5s**) because it is more free-tier friendly and less likely to keep instances warm.

---

## What you get

When collabx is running (locally or in the cloud) you get token-scoped endpoints:

- **Collector (GET/POST)**: `/{token}/c` (supports extra path segments)
- **Poll logs (JSON)**: `/{token}/logs?after_id=0&limit=50`
- **Stream logs (SSE, opt-in)**: `/{token}/events`
- **Health**: `/healthz`

The token is part of the path, so you can generate a new token per PoC and keep callbacks separated.

---

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
```

### For development

```bash
pip install -e ".[dev]"
```

This includes pytest, pytest-asyncio, pytest-cov, and ruff for testing and linting.

---

## Local quickstart

### Start the server

```bash
collabx init --url http://127.0.0.1:8080
TOKEN=$(collabx env --print-token)

collabx serve --host 127.0.0.1 --port 8080 --token "$TOKEN" --set-target
```

#### See the URL + token + endpoints (local)

```
collabx target show
```

This prints the base_url, the token, and the full endpoint URLs.

You can also print exports for use in other terminals:

```
collabx env
```

### Tail logs

In another terminal:

```
source .venv/bin/activate
collabx listen                 # poll mode default (5s)
# collabx listen --mode stream # opt-in SSE
```

### Send test callbacks (local)

GET:

```TOKEN=$(collabx env --print-token)
curl -i "http://127.0.0.1:8080/$TOKEN/c?hello=world&x=1"
```

POST:

```
TOKEN=$(collabx env --print-token)
curl -i -X POST "http://127.0.0.1:8080/$TOKEN/c" \
  -H "Content-Type: application/json" \
  -d '{"msg":"hi from local","id":123}'
```

Poll logs directly:

```
TOKEN=$(collabx env --print-token)
curl -s "http://127.0.0.1:8080/$TOKEN/logs?after_id=0&limit=10" | jq
```

## Cloud quickstart (GCP Cloud Run)

### Prereqs (you need all of these)

- A Google Cloud account
- A GCP project created in the Cloud Console
- Billing enabled on the project (Cloud Run/Build often require billing even if usage stays small)
- Docker installed and running locally
- Google Cloud SDK (gcloud) installed
- Your active gcloud account must have permission to use:
  - Cloud Run
  - Cloud Build
  - Artifact Registry

### Authenticate + select the project

```
gcloud auth login
gcloud auth list

gcloud config set project YOUR_PROJECT_ID
gcloud config get-value project
```

If you have multiple accounts configured, make sure the correct one is active:

```
gcloud config set account you@example.com
gcloud config get-value account
```

### Enable required APIs (one-time per project)

```PROJECT=$(gcloud config get-value project)

gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  --project "$PROJECT"
```

## IAM permissions (common failure)

If collabx up fails with PERMISSION_DENIED during gcloud builds submit, your active account does not have Cloud Build permissions in the project.

Typical roles needed for your user:

- roles/cloudbuild.builds.editor

- roles/run.admin

- roles/artifactregistry.writer

- roles/iam.serviceAccountUser

Also, the Cloud Build service account often needs permission to push images to Artifact Registry:

- roles/artifactregistry.writer for PROJECT_NUMBER@cloudbuild.gserviceaccount.com

If you are project admin, you can grant via CLI:

```
PROJECT=$(gcloud config get-value project)
USER="your-email@example.com"

gcloud projects add-iam-policy-binding "$PROJECT" \
  --member="user:$USER" --role="roles/cloudbuild.builds.editor"

gcloud projects add-iam-policy-binding "$PROJECT" \
  --member="user:$USER" --role="roles/run.admin"

gcloud projects add-iam-policy-binding "$PROJECT" \
  --member="user:$USER" --role="roles/artifactregistry.writer"

gcloud projects add-iam-policy-binding "$PROJECT" \
  --member="user:$USER" --role="roles/iam.serviceAccountUser"

PROJECT_NUMBER=$(gcloud projects describe "$PROJECT" --format="value(projectNumber)")

gcloud projects add-iam-policy-binding "$PROJECT" \
  --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
  --role="roles/artifactregistry.writer"
```

## Deploy

From the repo root:

```
collabx up --provider gcp --region us-central1
```

This will:

build + push the container image (Cloud Build → Artifact Registry)

deploy a new Cloud Run service

generate a token (unless you supplied one)

save the base_url + token as your active target

### See the deployed URL + token + endpoints (cloud)

```
collabx target show
```

You should see something like:

- base_url: https://...a.run.app

- token: <hex>

- collector: https://...a.run.app/<token>/c

- logs: https://...a.run.app/<token>/logs

- events: https://...a.run.app/<token>/events

You can also print exports for other terminals:

```
collabx env
```

### Tail logs

```
collabx listen                 # poll mode default (5s)
# collabx listen --mode stream # opt-in SSE
```

### Test the deployment (sample curl payloads)

Set convenience vars:

```
BASE=$(collabx target show | awk '/base_url:/ {print $2}')
TOKEN=$(collabx env --print-token)
```

1. Health check:

```
curl -i "$BASE/healthz"
```

2. GET callback (query string):

```
curl -i "$BASE/$TOKEN/c?proof=cloudrun&ts=$(date +%s)&hello=world"
```

3. POST callback (JSON body):

```
curl -i -X POST "$BASE/$TOKEN/c" \
  -H "Content-Type: application/json" \
  -d '{"poc":"collabx-cloudrun","marker":"abc123","nested":{"a":1,"b":true}}'
```

4. Poll logs directly:

```
curl -s "$BASE/$TOKEN/logs?after_id=0&limit=10" | jq
```

Important: Do not literally use <TOKEN> in URLs. Angle brackets will be URL-encoded and you will get 404s.
Use the real token value or TOKEN=$(collabx env --print-token).

## Status + teardown

```
collabx status
collabx down
```

### Optional:

```
collabx down --keep-image
collabx down --keep-state
```

### I deployed but want to stop paying

Run:

```
collabx down
```

That deletes the Cloud Run service and attempts to delete the pushed image tag.

### Endpoints

Core endpoints:

- `/{token}/c` (GET/POST) - Collector endpoint (supports extra path segments)
- `/{token}/logs` - Cursor-based polling with filtering support
- `/{token}/events` - SSE stream (opt-in)
- `/{token}/stats` - Collection statistics
- `/{token}/export` - Export logs in JSON, CSV, or NDJSON
- `/{token}/cleanup` - Delete old events (DELETE method)
- `/healthz` - Health check with uptime and version

### New Features (v0.4.0)

#### Statistics Endpoint

Get insights about your collected callbacks:

```bash
curl -s "$BASE/$TOKEN/stats" | jq
```

Returns:

- Total event count
- Events in last 24 hours
- Breakdown by HTTP method
- Unique IP addresses
- First and last event timestamps

#### Export Functionality

Download your logs in multiple formats:

```bash
# Export as JSON
curl -O "$BASE/$TOKEN/export?format=json"

# Export as CSV
curl -O "$BASE/$TOKEN/export?format=csv&limit=1000"

# Export as NDJSON (newline-delimited JSON)
curl -O "$BASE/$TOKEN/export?format=ndjson"
```

#### Filtering Logs

Filter logs by method or path:

```bash
# Get only POST requests
curl -s "$BASE/$TOKEN/logs?method=POST" | jq

# Get requests with specific path
curl -s "$BASE/$TOKEN/logs?path_contains=webhook" | jq

# Combine filters
curl -s "$BASE/$TOKEN/logs?method=GET&path_contains=api" | jq
```

#### Data Retention & Cleanup

Delete old events to manage storage:

```bash
# Delete events older than 7 days
curl -X DELETE "$BASE/$TOKEN/cleanup?days=7"

# Delete events older than 30 days
curl -X DELETE "$BASE/$TOKEN/cleanup?days=30"
```

#### Rate Limiting

Built-in rate limiting protects against abuse (60 requests/minute per IP by default).

Configure via environment variables:

```bash
export COLLABX_ENABLE_RATE_LIMIT=true
export COLLABX_RATE_LIMIT_PER_MINUTE=100
```

#### CORS Support

Enable CORS for browser-based testing:

```bash
export COLLABX_ENABLE_CORS=true
export COLLABX_CORS_ORIGINS="https://example.com,https://test.com"
```

### Configuration Options

All configuration via environment variables with `COLLABX_` prefix:

| Variable                        | Default           | Description                                    |
| ------------------------------- | ----------------- | ---------------------------------------------- |
| `COLLABX_TOKEN`                 | (required)        | Token(s) for authentication (comma-separated)  |
| `COLLABX_DB_PATH`               | `collabx.sqlite3` | SQLite database path                           |
| `COLLABX_ENABLE_RATE_LIMIT`     | `true`            | Enable rate limiting                           |
| `COLLABX_RATE_LIMIT_PER_MINUTE` | `60`              | Max requests per minute per IP                 |
| `COLLABX_ENABLE_CORS`           | `false`           | Enable CORS middleware                         |
| `COLLABX_CORS_ORIGINS`          | `*`               | Allowed CORS origins (comma-separated)         |
| `COLLABX_MAX_BODY_BYTES`        | `262144`          | Max body size to store (256KB)                 |
| `COLLABX_MAX_HEADER_BYTES`      | `8192`            | Max header size to store (8KB)                 |
| `COLLABX_RETENTION_DAYS`        | `30`              | Default retention period for events            |
| `COLLABX_REDACT_PATTERNS`       | `""`              | Regex patterns for redaction (comma-separated) |

### Testing

Run the test suite:

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/test_integration.py

# Run with verbose output
pytest -v
```

### API Documentation

When running locally, visit `http://127.0.0.1:8080/docs` for interactive API documentation (Swagger UI).

---
