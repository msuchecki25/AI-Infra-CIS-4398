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

## 6. Run the API locally

From the repository root, run:

```powershell
cd rawberry-api
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open the API documentation at:

<http://127.0.0.1:8000/docs>
