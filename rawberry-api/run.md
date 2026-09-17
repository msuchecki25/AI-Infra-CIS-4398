# Run RAWBerry API

## 1. Install the Google Cloud CLI

Install the Google Cloud CLI for Windows using the official installer:

<https://cloud.google.com/sdk/docs/install>

After installation, open a new PowerShell window so the `gcloud` command is available.

## 2. Check whether `gcloud` is installed

In PowerShell, run:

```powershell
gcloud --version
```

If the output includes something like `Google Cloud SDK`, the CLI is installed. If PowerShell says that `gcloud` is not recognized, install the Google Cloud CLI first and open a new PowerShell window.

## 3. Initialize `gcloud`

Run:

```powershell
gcloud init
```

A browser should open. Sign in with the Google account that has access to the `rawberryapi` project.

When prompted to select a project, choose:

```text
rawberryapi
```

Verify the active project afterward:

```powershell
gcloud config get-value project
```

Expected output:

```text
rawberryapi
```

## 4. Create local Application Default Credentials (ADC)

Run:

```powershell
gcloud auth application-default login
```

A browser will open again. Sign in and approve access.

Google stores the local ADC credentials on Windows at:

```text
%APPDATA%\gcloud\application_default_credentials.json
```

Do not copy this file into RAWBerry or commit it to GitHub. Google client libraries automatically search this ADC location.

## 5. Set the quota project

Associate the ADC credentials with `rawberryapi` for quota and billing purposes:

```powershell
gcloud auth application-default set-quota-project rawberryapi
```

## 6. Enable real Gemini chat

The API uses the mock response by default. In the same PowerShell window where you will run Uvicorn, set:

```powershell
$env:USE_MOCK_CHAT = "false"
$env:GOOGLE_CLOUD_PROJECT = "rawberryapi"
$env:GOOGLE_CLOUD_LOCATION = "global"
```

These variables remain available until you close the PowerShell window. If you open a new window, set them again. To save them permanently for future PowerShell windows, run:

```powershell
setx USE_MOCK_CHAT "false"
setx GOOGLE_CLOUD_PROJECT "rawberryapi"
setx GOOGLE_CLOUD_LOCATION "global"
```

After using `setx`, open a new PowerShell window. `.env.example` is only a template and is not loaded automatically by the current application.

## 7. Run the API locally

From the repository root, run:

```powershell
cd rawberry-api
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open the API documentation at:

<http://127.0.0.1:8000/docs>

## 8. Deploy to Google Cloud Run (public, beyond localhost)

This deploys the API as a container running on Google's infrastructure so
that other machines (teammates, the frontend, etc.) can reach it over the
internet — not just your own computer.

### Important: ADC is NOT used here

`gcloud auth application-default login` (steps 1–5 above) only authenticates
requests made **from your local machine** to Google Cloud. It has nothing to
do with how the deployed service authenticates once it's running on Cloud
Run.

When deployed, Cloud Run automatically attaches a **service account** to the
running container. The `google-genai` client in `app/services/gemini_service.py`
already uses Application Default Credentials discovery
(`genai.Client(vertexai=True, ...)`), and that discovery mechanism
automatically picks up the Cloud Run service account's credentials at
runtime instead of your local ADC file. **No code changes are required** —
the same code path works locally (via your personal ADC) and in Cloud Run
(via the service's attached service account).

### 8.1 Grant the Cloud Run service account access to Vertex AI

Cloud Run uses the default compute service account unless you specify one.
Find it and grant it the Vertex AI User role so it's allowed to call Gemini:

```powershell
$env:PROJECT_ID = "rawberryapi"
$env:PROJECT_NUMBER = (gcloud projects describe $env:PROJECT_ID --format="value(projectNumber)")

gcloud projects add-iam-policy-binding $env:PROJECT_ID `
  --member="serviceAccount:$($env:PROJECT_NUMBER)-compute@developer.gserviceaccount.com" `
  --role="roles/aiplatform.user"
```

If you deploy with a dedicated service account instead of the default one,
grant the role to that service account's email instead.

### 8.2 Deploy the container

From the repository root:

```powershell
cd rawberry-api

gcloud run deploy rawberry-api `
  --source . `
  --project rawberryapi `
  --region us-central1 `
  --allow-unauthenticated `
  --set-env-vars GOOGLE_CLOUD_PROJECT=rawberryapi,GOOGLE_CLOUD_LOCATION=global,GEMINI_MODEL=gemini-2.5-flash,USE_MOCK_CHAT=false
```

Notes:

- `--source .` tells Cloud Run to build the container image for you using
  Cloud Build and the `Dockerfile` in this folder — you don't need Docker
  installed locally, though the `Dockerfile` also lets you build/test the
  image locally if you want (`docker build -t rawberry-api .`).
- `--allow-unauthenticated` makes the endpoint public so other machines can
  call it without needing a Google identity token. Omit this flag (and add
  IAM invoker bindings instead) if you want to restrict access later.
- The `--set-env-vars` values mirror `.env.example`. Adjust the region if
  your team prefers a different one.
- The first deploy can take a few minutes while Cloud Build builds the image.

### 8.3 Get the service URL and test it

The deploy command prints a Service URL when it finishes, e.g.
`https://rawberry-api-xxxxxxxxxx-uc.a.run.app`. You can also fetch it later:

```powershell
gcloud run services describe rawberry-api --region us-central1 --format="value(status.url)"
```

Test it the same way you would locally:

```powershell
curl https://<your-service-url>/health
```

Or open the Swagger docs in a browser:

```text
https://<your-service-url>/docs
```

Any machine with network access can now reach these endpoints — no ADC,
`gcloud` install, or Google account required on their end.

### 8.4 Redeploying after code changes

Re-run the same `gcloud run deploy` command from step 8.2. Cloud Run will
build a new revision and shift traffic to it automatically.


