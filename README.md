# ZenML MLOps Platform on Kubernetes

Deploy ZenML self-hosted server on GKE using a local Helm chart and official MySQL image.

<!-- IMAGE: architecture diagram showing namespace zenml-server, MySQL pod, ZenML server pod, PVC, and port-forward to localhost:8080 -->

---

## Prerequisites

| Requirement | Version | Check |
| ----------- | ------- | ----- |
| kubectl | any | `kubectl version --client` |
| helm | >= 3.12 | `helm version` |
| Python | 3.12 | `python3 --version` |
| GKE cluster access | — | `kubectl get nodes` |

---

## Project Structure

```text
zenml-mlops-platform/
├── README.md               # This file — setup guide
├── runbook-zenml.md        # Detailed runbook + known issues
├── custom-values.yaml      # ZenML Helm overrides (DB URL, resources)
├── manifests/
│   └── mysql-official.yaml # MySQL manifest (Secret + Deployment + Service)
├── zenml/                  # ZenML Helm chart
│   ├── Chart.yaml
│   ├── values.yaml
│   └── templates/
└── examples/
    ├── smoke_test.py       # 2-step pipeline smoke test
    └── ml_pipeline.py      # 4-step ML pipeline with caching demo
```

---

## Step 1 — Create Namespace

```bash
kubectl create namespace zenml-server
```

---

## Step 2 — Deploy MySQL

> **Note:** Bitnami MySQL images are behind a paywall since Aug 2025.
> This setup uses the official `mysql:8.0` image from Docker Hub instead.

```bash
kubectl apply -f manifests/mysql-official.yaml
```

Wait for MySQL to be ready:

```bash
kubectl get pods -n zenml-server -w
```

<!-- IMAGE: terminal showing mysql-xxx pod reaching 1/1 Running status -->

Expected output:

```text
NAME                     READY   STATUS    RESTARTS   AGE
mysql-784885ddbd-xxxxx   1/1     Running   0          60s
```

### Verify MySQL connection

```bash
kubectl run mysql-test --rm -it --restart=Never \
  --image=mysql:8.0 \
  --namespace=zenml-server \
  -- mysql -h mysql.zenml-server.svc.cluster.local \
     -uroot -pYOUR_MYSQL_ROOT_PASSWORD \
     -e "SHOW DATABASES;"
```

<!-- IMAGE: terminal showing SHOW DATABASES output with 'zenml' database listed -->

Expected: database `zenml` appears in the list.

---

## Step 3 — Deploy ZenML Server

```bash
helm install zenml-server ./zenml \
  --namespace zenml-server \
  --values custom-values.yaml
```

Wait for all pods to be ready:

```bash
kubectl get pods -n zenml-server -w
```

<!-- IMAGE: terminal showing all 3 pods: mysql Running, zenml-server Running, db-migration Completed -->

Expected:

```text
NAME                                  READY   STATUS      AGE
mysql-784885ddbd-xxxxx                1/1     Running     5m
zenml-server-587fd6445b-xxxxx         1/1     Running     2m
zenml-server-db-migration-xxxxx       0/1     Completed   3m
```

> `Completed` on the migration pod is expected — it runs database schema setup once and exits.

---

## Step 4 — Fix user_metadata Column

Run this **once** after the migration pod completes:

```bash
kubectl run mysql-fix --rm -it --restart=Never \
  --image=mysql:8.0 \
  --namespace=zenml-server \
  -- mysql -h mysql.zenml-server.svc.cluster.local \
     -uroot -pYOUR_MYSQL_ROOT_PASSWORD \
     -e "ALTER TABLE zenml.user MODIFY COLUMN user_metadata TEXT;"
```

> **Why:** ZenML's default schema defines `user_metadata` as `VARCHAR(255)`.
> The onboarding survey JSON exceeds this limit. This fix expands it to `TEXT` (65KB).

---

## Step 5 — Access Admin UI

In a **dedicated terminal** (keep it running):

```bash
kubectl port-forward -n zenml-server svc/zenml-server 8080:80
```

Open your browser at <http://localhost:8080>

<!-- IMAGE: ZenML login/onboarding screen in browser at localhost:8080 -->

### Initial setup

1. Set **username** and **password** (min 8 chars, uppercase + lowercase + number + special char)
2. Set **Server Name** (e.g. `zenml-lab`)
3. Fill in **Name** and **Email**
4. Select **role**: Platform Engineer / MLOps Engineer
5. Select **AI types** and **challenges** as appropriate
6. Skip the Slack community step

<!-- IMAGE: ZenML onboarding screens — username/password, server name, role selection, AI types -->

---

## Step 6 — Install ZenML CLI

```bash
sudo apt install python3.12-venv -y

python3 -m venv ~/zenml-venv
source ~/zenml-venv/bin/activate

pip install "zenml==0.94.3"
```

> **Important:** Run `source ~/zenml-venv/bin/activate` every time you open a new terminal before using the `zenml` command.

---

## Step 7 — Create Service Account & Login

### Create API Key in Dashboard

1. Go to **Settings → Service Accounts**
2. Click **Create Service Account**
3. Name: `cli-user`, check **"Create a default API Key"**
4. Click **Add service account**
5. **Copy the API key immediately** — it is shown only once

<!-- IMAGE: Dashboard Settings → Service Accounts → Add service account dialog -->

<!-- IMAGE: API key display screen after service account creation — copy before closing -->

### Login via CLI

```bash
source ~/zenml-venv/bin/activate
zenml login http://127.0.0.1:8080 --api-key
# Paste the API key when prompted
```

Expected output:

```text
Authenticating to ZenML server 'http://127.0.0.1:8080' using an API key...
Setting the global active project to 'default'.
Setting the global active stack to default.
Updated the global store configuration.
```

<!-- IMAGE: terminal showing successful zenml login output -->

---

## Step 8 — Verify Stack

```bash
zenml stack list
zenml stack describe default
```

<!-- IMAGE: terminal showing zenml stack describe with ARTIFACT_STORE, ORCHESTRATOR, DEPLOYER all set to default and marked ACTIVE -->

Expected:

```text
Stack Configuration
╭────────────────┬────────────────╮
│ COMPONENT_TYPE │ COMPONENT_NAME │
├────────────────┼────────────────┤
│ ARTIFACT_STORE │ default        │
├────────────────┼────────────────┤
│ ORCHESTRATOR   │ default        │
├────────────────┼────────────────┤
│ DEPLOYER       │ default        │
╰────────────────┴────────────────╯
     'default' stack (ACTIVE)
```

---

## Step 9 — Smoke Test

```bash
python examples/smoke_test.py
```

<!-- IMAGE: terminal showing pipeline run output with both steps completed and Dashboard URL printed -->

Expected output:

```text
Initiating a new run for the pipeline: smoke_pipeline.
Registered new pipeline: smoke_pipeline.
Using user: cli-user
Using stack: default
Step ingest has started.
Step ingest has finished in 1.4s.
Step process has started.
Processed: HELLO FROM ZENML LAB
Step process has finished in 1.9s.
Pipeline run has finished in 7.9s.
```

### Verify in Dashboard

Open the Dashboard URL from the output, or go to **Pipelines → smoke_pipeline → latest run**

<!-- IMAGE: ZenML Dashboard showing smoke_pipeline run — Status: completed, 2/2 steps, DAG graph with ingest→output→process→output -->

Confirm:

- Status: **completed** ✅
- Total Steps: **2**, Completed: **2**
- DAG shows: `ingest → output → process → output`

---

## Credentials Reference

| Service | Access | Notes |
| ------- | ------ | ----- |
| MySQL | `mysql -uroot -pYOUR_MYSQL_ROOT_PASSWORD` | Via `kubectl run` client pod |
| ZenML Dashboard | <http://localhost:8080> | Requires active port-forward |
| ZenML CLI | `zenml login --api-key` | Requires `~/zenml-venv` activated |

---

## Troubleshooting

See [runbook-zenml.md](./runbook-zenml.md) for detailed known issues and fixes.

| Symptom | Fix |
| ------- | --- |
| MySQL pod `Init:ImagePullBackOff` | Use `manifests/mysql-official.yaml` — do not use bitnami image |
| `Data too long for column 'user_metadata'` | Run ALTER TABLE fix in Step 4 |
| `gio: Operation not supported` on `zenml login` | Use `--api-key` flag with Service Account key |
| ZenML pod `CrashLoopBackOff` | `kubectl logs -n zenml-server deploy/zenml-server` |
