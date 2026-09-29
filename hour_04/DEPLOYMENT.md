# Deployment and output verification

Run all commands from the project root. This guide prepares a synthetic workshop service. No cloud service has been created by this package.

## 1. Choose the runtime behavior

Local/Docker runs support durable approval state through SQLite when `.runtime` is preserved. Cloud Run disks can disappear between instances; the supplied cloud workflow therefore sets `HR_READ_ONLY=true` and does not expose working leave writes. Policy, balance, payroll, and calendar reads, multi-agent routing, tracing, and evaluation still run in the cloud.

Before enabling cloud writes, move **both** checkpoints and the transactional leave ledger to shared durable storage (for example a PostgreSQL checkpointer plus a transactional HR database), implement real employee/manager authorization, and test restart, duplicate-resume, and concurrent-write behavior. Setting `--max-instances 1` alone does not make instance-local SQLite durable.

## 2. Pre-provision Google Cloud

Have a project with billing, a chosen region, `gcloud`, Docker, and a GitHub repository. Set shell variables to your own values:

```bash
export PROJECT_ID=your-project-id
export REGION=asia-south1
gcloud auth login
gcloud config set project "$PROJECT_ID"
gcloud services enable run.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com iamcredentials.googleapis.com sts.googleapis.com
gcloud artifacts repositories create hr-workshop --repository-format=docker --location="$REGION"
gcloud iam service-accounts create hr-runtime --display-name='HR workshop runtime'
gcloud iam service-accounts create hr-deployer --display-name='HR workshop deployment'
```

If a resource already exists, reuse it instead of creating a duplicate. Runtime identity:

```text
hr-runtime@YOUR_PROJECT_ID.iam.gserviceaccount.com
```

Store three secrets in Secret Manager: `hr-openai`, `hr-langsmith`, and `hr-employee`. Use the Cloud Console's Secret Manager **Create secret** flow and enter the API keys/key value there. The employee key should be a generated secret rather than the local sample. Grant the runtime service account **Secret Manager Secret Accessor** on each of those three secrets. A manager secret is unnecessary for the read-only cloud deployment.

Grant the deployment service account:

- Artifact Registry Writer on the `hr-workshop` repository.
- Cloud Run Admin for creating/updating these workshop services and their invoker policy.
- Service Account User on the runtime service account.

Use your organization's IAM policy if it restricts these bindings. The pipeline uses `--allow-unauthenticated` so Cloud Run permits HTTP ingress; `/ask` still requires the application employee key, and the health/docs endpoints are public. If your organization forbids public ingress, remove that flag, grant Cloud Run Invoker to the caller, and supply `CLOUD_RUN_ID_TOKEN` for the smoke/evaluation clients.

Container deployment follows the [Cloud Run container deployment guide](https://docs.cloud.google.com/run/docs/deploying).

## 3. Configure GitHub OIDC authentication

Use Workload Identity Federation rather than a downloaded service-account private key. Create a workload identity pool/provider for GitHub's issuer `https://token.actions.githubusercontent.com`. Map `google.subject=assertion.sub` and `attribute.repository=assertion.repository`. Restrict the provider with an attribute condition matching your exact `OWNER/REPO`. Bind that repository's principal set to `roles/iam.workloadIdentityUser` on `hr-deployer`.

For copyable provisioning commands and organization-specific options, use the official [Google deployment-pipeline identity guide](https://cloud.google.com/iam/docs/workload-identity-federation-with-deployment-pipelines) and [GitHub authentication action](https://github.com/google-github-actions/auth). Do this before class; the workshop workflow consumes the existing provider.

In GitHub repository **Settings → Secrets and variables → Actions**, add:

| Type | Name | Value |
|---|---|---|
| Variable | `GCP_PROJECT_ID` | Your project ID |
| Variable | `GCP_REGION` | Your chosen region |
| Variable | `GCP_WIF_PROVIDER` | Full `projects/NUMBER/locations/global/workloadIdentityPools/POOL/providers/PROVIDER` name |
| Variable | `GCP_DEPLOY_SA` | `hr-deployer@PROJECT_ID.iam.gserviceaccount.com` |
| Variable | `GCP_RUNTIME_SA` | `hr-runtime@PROJECT_ID.iam.gserviceaccount.com` |
| Secret | `OPENAI_API_KEY` | Used by the evaluation judge |
| Secret | `LANGSMITH_API_KEY` | Used to create dataset and experiment |
| Secret | `HR_EMPLOYEE_API_KEY` | Same value as Secret Manager `hr-employee` |

The model and tracing keys used by the deployed app come from Secret Manager. GitHub secrets are used by the evaluator. Use the same LangSmith workspace/region for both. The example assumes the default US endpoint; for a different region, set the matching `LANGSMITH_ENDPOINT` in both workflow environment and Cloud Run environment.

## 4. Put the project at the repository root

Copy the contents of this project, including `.github/workflows/deploy.yml`, into the intended repository root. Keep `.env` and generated runtime data out of Git. The workflow expects `requirements.txt`, Dockerfile, `hr_agent`, and the hour folders at that root.

Commit and push through your normal repository workflow. In **Actions**, select **Build, deploy candidate, evaluate, promote**, then **Run workflow**. It is manually triggered so committing the starter kit does not launch a deployment automatically.

The job:

1. Installs the lock and runs local tests.
2. Builds an image tagged with the commit SHA and pushes it to Artifact Registry.
3. Deploys `hr-agent-candidate` with live mode, tracing, read-only mode, and Secret Manager bindings.
4. Runs the HTTP smoke test and the five-case LangSmith experiment against that candidate URL.
5. Uploads `eval-results.json`, if produced.
6. Deploys the same image to `hr-agent` only if those steps pass.
7. Smoke-tests the stable endpoint and writes its URL in the run summary.

A missing secret, missing score, HTTP failure, or evaluation below threshold makes the job fail. A failed candidate is left available for investigation; it is not promoted.

## 5. Verify the output yourself

```bash
gcloud run services describe hr-agent --project "$PROJECT_ID" --region "$REGION" --format='value(status.url)'
```

Copy the returned URL:

```bash
export HR_BASE_URL=https://YOUR-RETURNED-URL
export HR_EMPLOYEE_API_KEY=your-employee-key
curl -s "$HR_BASE_URL/health"
curl -s "$HR_BASE_URL/ask" \
  -H "X-API-Key: $HR_EMPLOYEE_API_KEY" -H 'Content-Type: application/json' \
  -d '{"question":"What is the carry forward policy?"}'
python -m pytest hour_04/test_live.py -q
```

Expect `mode: live`, a supported answer about up to 5 days, and `LEAVE-02`. The exact wording is not fixed. For the paid-sabbatical question, expect `not_in_policy`, `not in policy`, and no citations.

Open the LangSmith project `hr-agent-cloud`, inspect the request trace, then open the experiment named in the uploaded report. Record the service URL, GitHub run URL, image commit SHA, and LangSmith experiment URL together in your own delivery notes.

## 6. Diagnose or roll back

Check Cloud Run logs for startup errors, missing secrets, model access, or request timeouts. A health check only proves that the server started; the smoke test actually exercises policy retrieval and the agent.

If the stable service smoke test fails after promotion, inspect prior revisions:

```bash
gcloud run revisions list --service hr-agent --project "$PROJECT_ID" --region "$REGION"
gcloud run services update-traffic hr-agent --project "$PROJECT_ID" --region "$REGION" --to-revisions=YOUR_PREVIOUS_GOOD_REVISION=100
```

Use an actual verified prior revision. A first deployment has no prior good revision to restore. The workflow does not auto-roll back.

## 7. Hugging Face Docker Spaces fallback

Create a **Docker Space**, upload this project, and configure its Space README metadata with `sdk: docker` and `app_port: 8080`. Keep the workshop README body underneath that metadata. Add `OPENAI_API_KEY`, `LANGSMITH_API_KEY`, and `HR_EMPLOYEE_API_KEY` as Space secrets; set `HR_MODE=live`, `HR_READ_ONLY=true`, `LANGSMITH_TRACING=true`, and `PORT=8080` as variables. Deploy the existing Dockerfile, copy the Space application URL, and run the same HTTP smoke/evaluation commands against it.

This is a manual fallback, not a second GitHub deployment job. Availability, hardware, and account permissions depend on the provider. Follow the official [Docker Spaces guide](https://huggingface.co/docs/hub/spaces-sdks-docker). Keep read-only mode unless you deliberately configure durable state and appropriate identity controls.

## 8. End the workshop

To avoid leaving unused workshop services, delete `hr-agent-candidate` and `hr-agent` through Cloud Run when no longer needed. Remove unwanted images and secrets only after checking whether other work uses them. Keep the source project and validation report for the next session.
