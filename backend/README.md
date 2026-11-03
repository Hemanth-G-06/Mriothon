# Django Backend — AI Visual Quality Inspection System

Automated industrial visual quality inspection system for discrete manufacturing. Integrates the official **BIT-PLATE-CV-1.0** computer vision classifier with Django REST Framework, asynchronous Celery & Redis task queues, and SQLite/PostgreSQL persistence.

---

## 1. Cross-Platform Environment Compatibility

The backend dependency specification in `backend/requirements.txt` has been audited and verified for seamless installation on both **macOS (Apple Silicon ARM64 & Intel)** and **Windows (x64)** across **Python 3.10, 3.11, and 3.12**.

| Platform | Architecture | Supported Python | PyMuPDF Resolution | Pre-built Wheels |
| :--- | :--- | :--- | :--- | :--- |
| **macOS** | Apple Silicon ARM64 (`darwin-arm64`) | 3.10, 3.11, 3.12 | `1.28.2` (abi3 wheel) | Yes (Zero compilation) |
| **macOS** | Intel x86_64 (`darwin-x86_64`) | 3.10, 3.11, 3.12 | `1.28.2` (abi3 wheel) | Yes (Zero compilation) |
| **Windows** | AMD64 / x86_64 (`win_amd64`) | 3.10, 3.11, 3.12 | `1.28.2` (abi3 wheel) | Yes (Zero compilation) |
| **Linux** | x86_64 / ARM64 (`manylinux`) | 3.10, 3.11, 3.12 | `1.28.2` (abi3 wheel) | Yes (Zero compilation) |

---

## 2. Installation & Setup Guide

### A. macOS (Apple Silicon ARM64 / Intel)

#### Step 1: Install Redis & Python
```bash
# Install Redis via Homebrew
brew install redis

# Start Redis service (runs in background on port 6379)
brew services start redis

# Verify Redis connection
redis-cli ping
# Expected output: PONG
```

#### Step 2: Create and Activate Virtual Environment
```bash
cd backend

# Create an isolated virtual environment
python3 -m venv .venv

# Activate the virtual environment
source .venv/bin/activate

# Upgrade pip and packaging tools
pip install --upgrade pip setuptools wheel
```

#### Step 3: Install Backend Requirements
```bash
pip install -r requirements.txt
```

#### Step 4: Verify Installation Integrity
```bash
# 1. Verify no broken dependency constraints
python -m pip check
# Expected output: No broken requirements found.

# 2. Verify PyMuPDF and fitz imports
python -c "import pymupdf; import fitz; print('PyMuPDF Version:', pymupdf.__version__)"
# Expected output: PyMuPDF Version: 1.28.2

# 3. Verify Django system checks
python manage.py check
# Expected output: System check identified no issues (0 silenced).
```

---

### B. Windows (PowerShell / Command Prompt)

#### Step 1: Redis Setup on Windows
- **Option 1 (WSL 2 - Recommended):**
  ```bash
  wsl --install
  sudo apt-get update && sudo apt-get install redis-server -y
  sudo service redis-server start
  ```
- **Option 2 (Memurai for Windows / Redis MSI):**
  Download and run the Redis/Memurai Windows service on `127.0.0.1:6379`.

#### Step 2: Create and Activate Virtual Environment
```powershell
cd backend

# Create virtual environment
python -m venv .venv

# Activate in PowerShell
.\.venv\Scripts\Activate.ps1
# (Or in CMD: .venv\Scripts\activate.bat)

# Upgrade pip
python -m pip install --upgrade pip setuptools wheel
```

#### Step 3: Install Backend Requirements
```powershell
pip install -r requirements.txt
```

#### Step 4: Verify Installation Integrity
```powershell
python -m pip check
python -c "import pymupdf; import fitz; print('PyMuPDF Version:', pymupdf.__version__)"
python manage.py check
```

---

## 3. Database Initialization & Seeding

```bash
# 1. Apply database migrations
python manage.py migrate

# 2. Seed standard demo user accounts (Admin, Engineer, Supervisor)
python manage.py seed_demo_users

# 3. Seed default product component P-PLATE01
python -c "import django, os; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings'); django.setup(); from inspections.views import ensure_default_product_exists; ensure_default_product_exists()"
```

Demo User Credentials:
* **Administrator:** `sarah.connor@gmail.com` / `Admin@123`
* **Engineer:** `alex.vance@gmail.com` / `Engineer@123`
* **Supervisor:** `marcus.brody@gmail.com` / `Supervisor@123`

---

## 4. Running the Development Services

### Service 1: Django REST API Server
```bash
# From backend directory with .venv activated:
python manage.py runserver 8000
```
API endpoint available at: `http://127.0.0.1:8000/api/`

### Service 2: Celery Background Task Worker
On macOS and Windows, run with the `-P solo` pool execution model:
```bash
# macOS:
OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES celery -A config worker --loglevel=info -P solo

# Windows:
celery -A config worker --loglevel=info -P solo
```

---

## 5. Verification & Testing

### Run Inspection & Document Tests
```bash
python manage.py test inspections documents
```
Result: `Ran 55 tests ... OK`

### Run Complete Acceptance Test Suite
With Django, Celery, and Redis running:
```bash
python scripts/run_acceptance_test.py
```
Validates all 34 end-to-end acceptance assertions including single upload, batch processing, Celery task polling, supervisor review override, immutability, and RBAC 403 authorization denial.

### Run Official Model Evaluation (60 Images)
```bash
python scripts/evaluate_model.py
```
Evaluates `BIT-PLATE-CV-1.0` across 60 labeled samples, generating defect recall and confusion matrix.

---

## 6. Key Dependency Notes & Explanations

1. **`pymupdf>=1.24.14,<2.0`**:
   - `pymupdf==2.0` requires `Python >=3.11`. Python 3.10 environments cannot resolve it.
   - `PyMuPDF 1.28.2` provides pre-compiled Universal2 / ARM64 wheels for macOS (`macosx_11_0_arm64`) and Windows (`win_amd64`), supporting Python 3.10, 3.11, and 3.12 without requiring any native C++ compilers (`mupdf-c`).
   - Supports both `import pymupdf` and legacy `import fitz`.

2. **`google-genai>=2.30.0`**:
   - `google-genai 2.34.0` strictly requires `Python >=3.11`.
   - Setting `>=2.30.0` allows Python 3.10 to install stable `2.33.0`, and Python 3.11+ to install `2.34.0+`.

3. **`asgiref>=3.8.1,<4.0`**:
   - `asgiref 3.13.0` requires `Python >=3.11`.
   - Django 5.2 defines requirement `asgiref>=3.8.1,<4.0`, which resolves to `3.12.1` on Python 3.10 and `3.13.0` on Python 3.11+.

4. **`psycopg[binary]==3.3.6`**:
   - High-performance Psycopg 3 driver with pre-compiled C-extensions for PostgreSQL 18 / Neon cloud databases. Fallbacks automatically to SQLite if `DATABASE_URL` is omitted.

