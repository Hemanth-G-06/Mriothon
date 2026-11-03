# AI Visual Quality Inspection System — Round 2

Automated industrial visual quality inspection system for discrete manufacturing. Integrates the official **BIT-PLATE-CV-1.0** computer vision classifier with a **Django REST Framework** backend, asynchronous **Celery & Redis** task queues, and a responsive **React 18** frontend.

---

## 1. System Architecture

```
                    ┌────────────────────────────┐
                    │    React 18 Frontend UI    │
                    │ (Vite + Bootstrap + Lucide)│
                    └─────────────┬──────────────┘
                                  │ Axios / JWT
                                  ▼
                    ┌────────────────────────────┐
                    │   Django REST Framework    │
                    │  (RBAC, Validation, ORM)   │
                    └──────┬──────────────┬──────┘
                           │              │
         [Single Upload]   │              │   [Batch Upload 1–10 Images]
         Synchronous       │              │   Enqueues Celery Tasks
                           ▼              ▼
           ┌──────────────────────┐  ┌──────────────────────┐
           │ Pillow Image Decoder │  │ Redis Message Broker │
           │  & Content Validator │  │  (127.0.0.1:6379)    │
           └──────────┬───────────┘  └──────────┬───────────┘
                      │                         │
                      ▼                         ▼
           ┌──────────────────────┐  ┌──────────────────────┐
           │ Official Model       │  │ Celery Worker        │
           │ BIT-PLATE-CV-1.0     │◄─┤ (Background Tasks    │
           │ (17-D Features + LR) │  │  & Fault Isolation)  │
           └──────────┬───────────┘  └──────────┬───────────┘
                      │                         │
                      └──────────┬──────────────┘
                                 │ Persist Results
                                 ▼
                    ┌────────────────────────────┐
                    │ Relational Database Storage│
                    │  (PostgreSQL / SQLite WAL) │
                    └────────────────────────────┘
```

---

## 2. Official Model Integration

* **Model Version:** `BIT-PLATE-CV-1.0`
* **Target Product:** `P-PLATE01` (Demonstration metal plate)
* **Classes:** Class 0: `Normal` | Class 1: `Defective`
* **Architecture:** Fixed 128x128 bilinear preprocessing, central crop (16:112), 17 standardized image features, logistic regression with 0.5 decision threshold.
* **Inference Pipeline:** Directly imports `predict(image_path)` from `Model/inference.py` and loads frozen weights from `Model/classifier.npz`.
* **Immutability:** Original automated predictions, confidence scores, defect probabilities, and model version strings remain permanently immutable in the database. Supervisor audit overrides are tracked separately.

---

## 3. Strict Image Upload Validation

Server-side validation uses Pillow decoding prior to calling the AI model:
1. **Formats:** JPEG (`.jpg`, `.jpeg`) and PNG (`.png`) only. Content inspected via PIL header decoding.
2. **File Size Limit:** Maximum 5 MiB (5,242,880 bytes).
3. **Dimensions:** Minimum 64 x 64 pixels; maximum 4096 x 4096 pixels.
4. **Integrity:** Zero-byte files, corrupted files, and misleading extensions (e.g., text with `.jpg`) are rejected.
5. **Batch Constraints:** 1 to 10 images per batch.
6. **Fault Isolation:** Corrupted or invalid files within a batch are recorded as failed attempts with readable failure reasons and **no AI prediction**, while valid files continue through inference.

---

## 4. Role-Based Access Control (RBAC)

Enforced strictly on the server:
* **Administrator (`sarah.connor@gmail.com` / `Admin@123`):** Product registration, access to all inspection records, galleries, and plant telemetry.
* **Engineer (`alex.vance@gmail.com` / `Engineer@123`):** Single and batch image submissions; view personal inspection history only. **Direct review calls return HTTP 403 Forbidden.**
* **Supervisor (`marcus.brody@gmail.com` / `Supervisor@123`):** Access to all inspection records; submit quality audit reviews (Confirm / Correct with comments).

---

## 5. Quick Start Instructions

Ensure **Redis** is running before starting the Celery worker and Django server.

### Redis Startup

* **macOS (Homebrew):**
  ```bash
  brew services start redis
  # or directly:
  redis-server
  ```
  Verify with: `redis-cli ping` (should output `PONG`).

* **Linux / Ubuntu / WSL:**
  ```bash
  sudo service redis-server start
  ```

---

### Terminal 1 — Django Backend

```bash
cd backend

# 1. Create and activate isolated virtual environment
python3 -m venv .venv
source .venv/bin/activate       # On Windows: .venv\Scripts\Activate.ps1

# 2. Install dependencies (verified on macOS ARM64 and Windows x64)
pip install -r requirements.txt

# 3. Run database migrations
python manage.py migrate

# 4. Seed demo accounts (Admin, Engineer, Supervisor) & Product P-PLATE01
python manage.py seed_demo_users
python -c "import django, os; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings'); django.setup(); from inspections.views import ensure_default_product_exists; ensure_default_product_exists()"

# 5. Start HTTP API server
python manage.py runserver 8000
```
API runs on: `http://127.0.0.1:8000/api/`

---

### Terminal 2 — Celery Background Worker

```bash
cd backend
source .venv/bin/activate       # On Windows: .venv\Scripts\Activate.ps1

# macOS:
OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES celery -A config worker --loglevel=info -P solo

# Windows:
celery -A config worker --loglevel=info -P solo
```

---

### Terminal 3 — React Frontend

```bash
cd frontend

# 1. Install dependencies
npm install

# 2. Launch Vite dev server
npm run dev
```
UI runs on: `http://localhost:5173/`

---

## 6. Official Model Evaluation & Metrics

Run the evaluation script across all 60 labeled sample images:

```bash
python3 backend/scripts/evaluate_model.py
```

### Evaluation Results (Samples/labels.csv)

```
======================================================================
 ROUND 2 AI QUALITY INSPECTION — MODEL EVALUATION REPORT
======================================================================
Model Identifier      : BIT-PLATE-CV-1.0
Total Sample Count    : 60
Successful Predictions: 60
Failed Predictions    : 0
----------------------------------------------------------------------
CONFUSION MATRIX:
                     Predicted Normal    Predicted Defective    Total
  Actual Normal              30                   0                30
  Actual Defective            0                  30                30
  Total                      30                  30                60
----------------------------------------------------------------------
CLASSIFICATION COUNTS:
  True Positives  (TP) : 30  (Actual Defective, Predicted Defective)
  True Negatives  (TN) : 30  (Actual Normal, Predicted Normal)
  False Positives (FP) : 0  (Actual Normal, Predicted Defective)
  False Negatives (FN) : 0  (Actual Defective, Predicted Normal)
----------------------------------------------------------------------
PERFORMANCE METRICS:
  Defect Recall (TP / (TP + FN)) : 1.0000 (100.00%)
  Precision    (TP / (TP + FP)) : 1.0000 (100.00%)
  Accuracy                       : 1.0000 (100.00%)
  F1-Score                       : 1.0000
----------------------------------------------------------------------
LIMITATIONS:
  Evaluated on 60 synthetic procedural illustrations under fixed framing and lighting.
  No real factory photos or domain shifts were present. Scores are uncalibrated model outputs.
======================================================================
```

---

## 7. Automated Test Suite

Run the unit and integration tests:

```bash
cd backend

# Run inspection tests (22 tests covering RBAC, validation, Celery, AI model)
python3 manage.py test inspections

# Run full suite including authentication (68 tests total)
python3 manage.py test
```

### End-to-End Acceptance Verification

With Redis, Django, and Celery running, execute the automated acceptance script:

```bash
python3 backend/scripts/run_acceptance_test.py
```
Validates all 34 end-to-end acceptance criteria including live token generation, single image scoring, mixed batch Celery processing, supervisor review calibration, and engineer 403 authorization denial.

---

## 8. REST API Reference

| Endpoint | Method | Role | Description |
| :--- | :--- | :--- | :--- |
| `/api/auth/login/` | `POST` | Public | Obtain JWT access and refresh tokens |
| `/api/auth/refresh/` | `POST` | Public | Refresh expired access token |
| `/api/auth/me/` | `GET` | Authenticated | Retrieve current user profile and role |
| `/api/products/` | `GET` | Authenticated | List all registered products |
| `/api/products/` | `POST` | **Admin** | Register new product (P-PLATE01) |
| `/api/products/<id>/` | `GET` | Authenticated | Retrieve specifications for product |
| `/api/inspections/single/` | `POST` | **Engineer/Admin** | Upload single plate image for synchronous inference |
| `/api/inspections/batch/` | `POST` | **Engineer/Admin** | Upload batch (1–10 images) for Celery processing |
| `/api/inspections/batch/<id>/` | `GET` | Authenticated | Poll batch progress and item statuses |
| `/api/inspections/` | `GET` | Authenticated | Query inspection history (Engineer scoped) |
| `/api/inspections/<id>/` | `GET` | Authenticated | Query inspection details |
| `/api/supervisor/inspections/` | `GET` | **Supervisor/Admin** | Retrieve supervisor review queue |
| `/api/inspections/<id>/review/` | `POST` | **Supervisor/Admin** | Submit confirm or correct review |
| `/api/health/` | `GET` | Public | System health check |

