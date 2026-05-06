# ZenML MLOps Platform on Kubernetes

> ระบบ MLOps Platform สำหรับจัดการ ML Pipeline บน Kubernetes โดยใช้ Helm chart และ MySQL official image
>
> Self-hosted ZenML server deployment on GKE using local Helm chart and official MySQL image.

<!-- IMAGE: architecture diagram showing namespace zenml-server, MySQL pod, ZenML server pod, PVC, and port-forward to localhost:8080 -->

---

## สิ่งที่ต้องมีก่อนเริ่ม / Prerequisites

| สิ่งที่ต้องการ / Requirement | เวอร์ชัน / Version | ตรวจสอบ / Check |
| ----------------------------- | ------------------ | --------------- |
| kubectl | any | `kubectl version --client` |
| helm | >= 3.12 | `helm version` |
| Python | 3.12 | `python3 --version` |
| GKE cluster access | — | `kubectl get nodes` |

---

## โครงสร้างโปรเจกต์ / Project Structure

```text
zenml-mlops-platform/
├── README.md               # คู่มือการติดตั้ง / Setup guide
├── custom-values.yaml      # ค่า config สำหรับ ZenML Helm / ZenML Helm overrides
├── manifests/
│   └── mysql-official.yaml # Kubernetes manifest สำหรับ MySQL
├── zenml/                  # ZenML Helm chart (local)
│   ├── Chart.yaml
│   ├── values.yaml
│   └── templates/
└── examples/
    ├── smoke_test.py       # Pipeline ทดสอบ 2 steps / 2-step smoke test
    └── ml_pipeline.py      # Pipeline ตัวอย่าง 4 steps + caching demo
```

---

## Admin UI

**ZenML Dashboard** เข้าใช้งานผ่าน port-forward:

```bash
kubectl port-forward -n zenml-server svc/zenml-server 8080:80
```

เปิด browser ที่ / Open browser at: **http://localhost:8080**

<!-- IMAGE: ZenML Dashboard หน้าหลักหลัง login สำเร็จ -->

---

## ขั้นตอนการติดตั้ง / Installation Steps

### ขั้นตอนที่ 1 — สร้าง Namespace / Create Namespace

```bash
kubectl create namespace zenml-server
```

---

### ขั้นตอนที่ 2 — ติดตั้ง MySQL / Deploy MySQL

> **หมายเหตุ / Note:** Bitnami MySQL image ถูกล็อกไม่ให้ใช้ฟรีตั้งแต่ Aug 2025
> จึงใช้ official `mysql:8.0` image จาก Docker Hub แทน
>
> Bitnami MySQL images are behind a paywall since Aug 2025.
> This setup uses the official `mysql:8.0` image from Docker Hub instead.

**แก้ไข password ใน `manifests/mysql-official.yaml` ก่อน:**

```yaml
stringData:
  root-password: "YOUR_MYSQL_ROOT_PASSWORD"  # เปลี่ยนเป็น password จริง
```

**แล้วรัน / Then apply:**

```bash
kubectl apply -f manifests/mysql-official.yaml
kubectl get pods -n zenml-server -w
```

<!-- IMAGE: terminal แสดง mysql pod สถานะ 1/1 Running -->

ผลที่ต้องเห็น / Expected:

```text
NAME                     READY   STATUS    RESTARTS   AGE
mysql-784885ddbd-xxxxx   1/1     Running   0          60s
```

**ตรวจสอบ MySQL / Verify MySQL:**

```bash
kubectl run mysql-test --rm -it --restart=Never \
  --image=mysql:8.0 \
  --namespace=zenml-server \
  -- mysql -h mysql.zenml-server.svc.cluster.local \
     -uroot -pYOUR_MYSQL_ROOT_PASSWORD \
     -e "SHOW DATABASES;"
```

<!-- IMAGE: terminal แสดง SHOW DATABASES ที่มี database 'zenml' อยู่ในรายการ -->

ต้องเห็น database `zenml` ในรายการ / Expected: database `zenml` in the list.

---

### ขั้นตอนที่ 3 — ติดตั้ง ZenML Server / Deploy ZenML Server

**แก้ไข password ใน `custom-values.yaml` ก่อน:**

```yaml
server:
  database:
    url: "mysql://root:YOUR_MYSQL_ROOT_PASSWORD@mysql.zenml-server.svc.cluster.local:3306/zenml"
```

**แล้วรัน / Then install:**

```bash
helm install zenml-server ./zenml \
  --namespace zenml-server \
  --values custom-values.yaml

kubectl get pods -n zenml-server -w
```

<!-- IMAGE: terminal แสดง pods ทั้ง 3 ตัว: mysql Running, zenml-server Running, db-migration Completed -->

ผลที่ต้องเห็น / Expected:

```text
NAME                                  READY   STATUS      AGE
mysql-784885ddbd-xxxxx                1/1     Running     5m
zenml-server-587fd6445b-xxxxx         1/1     Running     2m
zenml-server-db-migration-xxxxx       0/1     Completed   3m
```

> `Completed` บน migration pod คือปกติ — รัน schema setup ครั้งเดียวแล้วจบ
>
> `Completed` on the migration pod is expected — runs schema setup once and exits.

---

### ขั้นตอนที่ 4 — แก้ไข user_metadata Column / Fix user_metadata Column

รันคำสั่งนี้ **ครั้งเดียว** หลัง migration pod Completed:

```bash
kubectl run mysql-fix --rm -it --restart=Never \
  --image=mysql:8.0 \
  --namespace=zenml-server \
  -- mysql -h mysql.zenml-server.svc.cluster.local \
     -uroot -pYOUR_MYSQL_ROOT_PASSWORD \
     -e "ALTER TABLE zenml.user MODIFY COLUMN user_metadata TEXT;"
```

> **ทำไม / Why:** ZenML สร้าง column `user_metadata` เป็น `VARCHAR(255)` ซึ่งเล็กเกินไปสำหรับ JSON onboarding survey
> การแก้ไขนี้ขยายเป็น `TEXT` (65KB)
>
> ZenML's default schema defines `user_metadata` as `VARCHAR(255)`.
> This fix expands it to `TEXT` (65KB) to prevent onboarding survey overflow.

---

### ขั้นตอนที่ 5 — เข้าใช้งาน Admin UI / Access Admin UI

เปิด terminal แยก (ค้างไว้ตลอด) / In a dedicated terminal (keep it running):

```bash
kubectl port-forward -n zenml-server svc/zenml-server 8080:80
```

เปิด browser ที่ / Open: **http://localhost:8080**

<!-- IMAGE: ZenML onboarding screens — username/password, server name, role selection, AI types -->

**ขั้นตอน onboarding / Initial setup:**

1. ตั้ง **username** และ **password** (อย่างน้อย 8 ตัว, มีตัวใหญ่ + ตัวเล็ก + ตัวเลข + special char)
2. ตั้งชื่อ **Server Name** เช่น `zenml-lab`
3. กรอก **ชื่อและอีเมล / Name and Email**
4. เลือก **role**: Platform Engineer / MLOps Engineer
5. เลือก **AI types** และ **challenges** ตามต้องการ
6. กด Skip สำหรับ Slack community

---

### ขั้นตอนที่ 6 — ติดตั้ง ZenML CLI / Install ZenML CLI

```bash
sudo apt install python3.12-venv -y

python3 -m venv ~/zenml-venv
source ~/zenml-venv/bin/activate

pip install "zenml==0.94.3"
```

> **สำคัญ / Important:** รัน `source ~/zenml-venv/bin/activate` ทุกครั้งที่เปิด terminal ใหม่ก่อนใช้ `zenml` command

---

### ขั้นตอนที่ 7 — สร้าง Service Account และ Login / Create Service Account & Login

**สร้าง API Key จาก Dashboard / Create API Key in Dashboard:**

1. ไปที่ / Go to **Settings → Service Accounts**
2. กด / Click **Create Service Account**
3. ชื่อ / Name: `cli-user` — ติ๊ก / check **"Create a default API Key"**
4. กด / Click **Add service account**
5. **Copy API key ทันที** — แสดงครั้งเดียวเท่านั้น / shown only once

<!-- IMAGE: Dashboard Settings → Service Accounts → Add service account dialog -->

<!-- IMAGE: หน้าแสดง API key หลังสร้าง Service Account — copy ก่อนปิด -->

**Login ผ่าน CLI / Login via CLI:**

```bash
source ~/zenml-venv/bin/activate
zenml login http://127.0.0.1:8080 --api-key
# วาง API key เมื่อถูกถาม / Paste the API key when prompted
```

ผลที่ต้องเห็น / Expected:

```text
Authenticating to ZenML server 'http://127.0.0.1:8080' using an API key...
Setting the global active project to 'default'.
Setting the global active stack to default.
Updated the global store configuration.
```

<!-- IMAGE: terminal แสดง zenml login สำเร็จ -->

---

### ขั้นตอนที่ 8 — ตรวจสอบ Stack / Verify Stack

```bash
zenml stack list
zenml stack describe default
```

<!-- IMAGE: terminal แสดง zenml stack describe พร้อม ARTIFACT_STORE, ORCHESTRATOR, DEPLOYER ครบ และ ACTIVE -->

ผลที่ต้องเห็น / Expected:

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

### ขั้นตอนที่ 9 — Smoke Test

```bash
python examples/smoke_test.py
```

<!-- IMAGE: terminal แสดง pipeline run output ทั้ง 2 steps เสร็จพร้อม Dashboard URL -->

ผลที่ต้องเห็น / Expected:

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

**ตรวจสอบใน Dashboard / Verify in Dashboard:**

ไปที่ / Go to: **Pipelines → smoke_pipeline → latest run**

<!-- IMAGE: ZenML Dashboard แสดง smoke_pipeline run — Status: completed, 2/2 steps, DAG graph -->

ยืนยัน / Confirm:

- Status: **completed** ✅
- Total Steps: **2**, Completed: **2**
- DAG: `ingest → output → process → output`

---

## Credentials Reference

| บริการ / Service | การเข้าถึง / Access | หมายเหตุ / Notes |
| ---------------- | ------------------- | ---------------- |
| MySQL | `mysql -uroot -pYOUR_MYSQL_ROOT_PASSWORD` | ผ่าน `kubectl run` client pod |
| ZenML Dashboard | <http://localhost:8080> | ต้องเปิด port-forward ไว้ |
| ZenML CLI | `zenml login --api-key` | ต้อง activate `~/zenml-venv` ก่อน |

---

## การแก้ไขปัญหา / Troubleshooting

| อาการ / Symptom | วิธีแก้ / Fix |
| --------------- | ------------- |
| MySQL pod `Init:ImagePullBackOff` | ใช้ `manifests/mysql-official.yaml` — ห้ามใช้ bitnami image |
| `Data too long for column 'user_metadata'` | รัน ALTER TABLE fix ใน Step 4 |
| `gio: Operation not supported` ตอน `zenml login` | ใช้ `--api-key` flag กับ Service Account key |
| ZenML pod `CrashLoopBackOff` | `kubectl logs -n zenml-server deploy/zenml-server` |
