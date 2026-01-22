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

---

## Local quickstart

### Start the server

```bash
collabx init --url http://127.0.0.1:8080
TOKEN=$(collabx env --print-token)

collabx serve --host 127.0.0.1 --port 8080 --token "$TOKEN" --set-target
```

### Get the endpoints to use (local)

```bash
collabx target show
```

This prints the `base_url` and the full endpoints, for example:

- collector: `http://127.0.0.1:8080/<token>/c`
- logs:      `http://127.0.0.1:8080/<token>/logs`
- events:    `http://127.0.0.1:8080/<token>/events`

You can also print exports for other terminals:

```bash
collabx env
```

### Tail logs (poll default)

In another terminal:

```bash
source .venv/bin/activate
collabx listen                 # poll mode default (5s)
# collabx listen --mode stream # opt-in SSE
```

### Send test callbacks (local)

GET (query string):

```bash
TOKEN=$(collabx env --print-token)
curl -i "http://127.0.0.1:8080/$TOKEN/c?hello=world&x=1"
```

POST (JSON body):

```bash
TOKEN=$(collabx env --print-token)
curl -i -X POST "http://127.0.0.1:8080/$TOKEN/c"   -H "Content-Type: application/json"   -d '{"msg":"hi from local","id":123}'
```

Poll logs directly:

```bash
TOKEN=$(collabx env --print-token)
curl -s "http://127.0.0.1:8080/$TOKEN/logs?after_id=0&limit=10" | jq
```

---

## Cloud quickstart (GCP Cloud Run)

### Prereqs (you need all of these)

- A **Google Cloud account**
- A **GCP project** created in the Cloud Console
- **Billing enabled** on the project (Cloud Run/Build often require billing even if usage stays small)
- **Docker** installed and running locally
- **Google Cloud SDK (`gcloud`)** installed
- Your active `gcloud` account must have permission to use:
  - Cloud Run
  - Cloud Build
  - Artifact Registry

### Authenticate + select the project

```bash
gcloud auth login
gcloud auth list

gcloud config set project YOUR_PROJECT_ID
gcloud config get-value project
```

If you have multiple accounts configured, make sure the correct one is active:

```bash
gcloud config set account you@example.com
gcloud config get-value account
```

### Enable required APIs (one-time per project)

```bash
PROJECT=$(gcloud config get-value project)

gcloud services enable   run.googleapis.com   cloudbuild.googleapis.com   artifactregistry.googleapis.com   --project "$PROJECT"
```

### IAM permissions (common failure)

If `collabx up` fails with `PERMISSION_DENIED` during `gcloud builds submit`, your active account does not have Cloud Build permissions in the project.

Typical roles needed for **your user**:
- `roles/cloudbuild.builds.editor`
- `roles/run.admin`
- `roles/artifactregistry.writer`
- `roles/iam.serviceAccountUser`

Also, the **Cloud Build service account** often needs permission to push images to Artifact Registry:
- `roles/artifactregistry.writer` for `PROJECT_NUMBER@cloudbuild.gserviceaccount.com`

If you are project admin, you can grant via CLI:

```bash
PROJECT=$(gcloud config get-value project)
USER="your-email@example.com"

gcloud projects add-iam-policy-binding "$PROJECT"   --member="user:$USER" --role="roles/cloudbuild.builds.editor"

gcloud projects add-iam-policy-binding "$PROJECT"   --member="user:$USER" --role="roles/run.admin"

gcloud projects add-iam-policy-binding "$PROJECT"   --member="user:$USER" --role="roles/artifactregistry.writer"

gcloud projects add-iam-policy-binding "$PROJECT"   --member="user:$USER" --role="roles/iam.serviceAccountUser"

PROJECT_NUMBER=$(gcloud projects describe "$PROJECT" --format="value(projectNumber)")

gcloud projects add-iam-policy-binding "$PROJECT"   --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com"   --role="roles/artifactregistry.writer"
```

### Deploy

From the repo root:

```bash
collabx up --provider gcp --region us-central1
```

This will:
- build + push the container image (Cloud Build → Artifact Registry)
- deploy a new Cloud Run service
- generate a token (unless you supplied one)
- save the `base_url` + token as your active target

### Get the cloud URL and endpoints

```bash
collabx target show
```

Look for:

- `base_url:  https://...a.run.app`
- `token:     <hex>`
- `collector: https://...a.run.app/<token>/c`
- `logs:      https://...a.run.app/<token>/logs`
- `events:    https://...a.run.app/<token>/events`

You can also print exports:

```bash
collabx env
```

### Tail logs

```bash
collabx listen                 # poll mode default (5s)
# collabx listen --mode stream # opt-in SSE
```

### Test once deployed

```bash
BASE=$(collabx target show | awk '/base_url:/ {print $2}')
TOKEN=$(collabx env --print-token)

curl -i "$BASE/$TOKEN/c?hello=world&x=1"
curl -i -X POST "$BASE/$TOKEN/c"   -H "Content-Type: application/json"   -d '{"msg":"hi from cloud","id":123}'

curl -i "$BASE/healthz"
curl -s "$BASE/$TOKEN/logs?after_id=0&limit=10" | jq
```

**Important:** Do not literally use `<TOKEN>` in URLs. Angle brackets will be URL-encoded and you will get 404s.
Use the real token value or `TOKEN=$(collabx env --print-token)`.

### Status + teardown

```bash
collabx status
collabx down
```

Optional:

```bash
collabx down --keep-image
collabx down --keep-state
```

---

## Troubleshooting

### `PERMISSION_DENIED` on `gcloud builds submit`

Symptom:
- `ERROR: (gcloud.builds.submit) PERMISSION_DENIED: The caller does not have permission...`

Fix checklist:
1) Confirm the **active account** and **project**:

```bash
gcloud config get-value account
gcloud config get-value project
```

2) Make sure **billing is enabled** on the project (Cloud Console → Billing).

3) Ensure required APIs are enabled:

```bash
PROJECT=$(gcloud config get-value project)
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com --project "$PROJECT"
```

4) Grant roles to your user and to the Cloud Build service account (see IAM section above).

---

### `No target set`

Run one of:
- `collabx init --url http://127.0.0.1:8080` (local)
- `collabx up --provider gcp --region us-central1` (cloud)
- or manually set: `collabx target set --url ... --token ...`

---

### 404 when polling logs (`/{token}/logs`)

Most common causes:
- You used a placeholder like `<TOKEN>` instead of the real token.
- You are using the wrong token for the current server.

Fix:

```bash
collabx target show
TOKEN=$(collabx env --print-token)
```

Then retry:

```bash
BASE=$(collabx target show | awk '/base_url:/ {print $2}')
curl -i "$BASE/$TOKEN/logs?after_id=0&limit=1"
```

---

### SSE stream does not show events

SSE can be affected by proxies/buffering. Try polling first:

```bash
collabx listen
```

If you still want SSE:

```bash
collabx listen --mode stream
```

And test the stream directly:

```bash
BASE=$(collabx target show | awk '/base_url:/ {print $2}')
TOKEN=$(collabx env --print-token)
curl -N -H "Accept: text/event-stream" "$BASE/$TOKEN/events"
```

---

### Docker / build issues

If builds fail early, confirm Docker is installed and running:

```bash
docker ps
```

Also confirm gcloud can run builds:

```bash
gcloud builds list --limit 1
```

---

### I deployed but want to stop paying

Run:

```bash
collabx down
```

That deletes the Cloud Run service and attempts to delete the pushed image tag.

---

## Endpoints

- `/{token}/c` (GET/POST) collector (supports extra path segments)
- `/{token}/logs` cursor-based polling
- `/{token}/events` SSE stream (opt-in)
- `/healthz`
