# AI Visual Quality Inspection System for Manufacturing

## Round 2 Technical Documentation & System Reference

---

## 1. Project Overview

The **AI Visual Quality Inspection System for Manufacturing** is an automated quality assurance and computer vision platform designed for discrete manufacturing production lines. Developed for Round 2 of the hackathon challenge, the system automates visual inspection of precision metal base plates (component identifier `P-PLATE01`) to detect physical manufacturing anomalies, structural defects, surface irregularities, and machining imperfections.

In industrial manufacturing, visual quality inspection ensures that components adhere to strict physical tolerances before passing to downstream assembly. This system introduces an automated inspection pipeline that classifies inspected metal plate images into two operational categories:

*   **Normal:** The component exhibits uniform surface topology, regular byte entropy, and smooth gradient transitions compliant with quality benchmarks.
*   **Defective:** The component displays physical surface defects, hairline fractures, voids, porosity, edge burrs, or machining abrasions exceeding allowable tolerance thresholds.

The system provides dedicated portals for **Plant Administrators**, **Quality Engineers**, and **Quality Supervisors**. It combines deterministic image validation, single and batch inspection modes, persistent database audit records, and human-in-the-loop supervisor verification.

---

## 2. Problem Statement

Quality inspection on modern manufacturing lines encounters several fundamental operational challenges:

1.  **Manual Inspection Vulnerability:** Human operators experience fatigue, eye strain, and attentional variance during extended shifts, resulting in inconsistent defect escape rates.
2.  **Subjectivity and Inconsistency:** Borderline surface imperfections are judged differently across inspectors, causing unpredictable quality releases.
3.  **Production Bottlenecks:** Manual visual inspection cannot keep pace with high-speed automated milling and stamping processes, often restricting plants to low-percentage lot sampling.
4.  **Audit Traceability Gaps:** Traditional inspection workflows fail to capture immutable digital records linking raw images, automated classifications, timestamps, engineer identities, and supervisor approvals.
5.  **Absence of Calibration Feedback:** When misclassifications occur, traditional setups lack structured override mechanisms that preserve original machine predictions for defect calibration.

The **AI Visual Quality Inspection System** addresses these issues by delivering an automated software pipeline featuring deterministic validation, sub-second inference, sequential batch uploads of up to 10 images with individual fault isolation, and a non-destructive supervisor review workflow.

---

## 3. Project Objectives

*   **Automated Quality Classification:** Classify manufactured metal plate images into `Normal` and `Defective` states.
*   **Integrated Computer Vision Inference:** Implement a dedicated computer vision engine (`BIT-PLATE-CV-1.0`) capable of binary header validation, Shannon entropy calculation, and gradient anomaly scoring without external C-extension dependencies.
*   **Flexible Inspection Workflows:** Provide both single-image drag-and-drop inspection and batch inspection (1–10 images) with individual item failure isolation.
*   **Audit Trail Persistence:** Store raw image files, calculated probabilities, model versions, and submitting engineer metadata in an indexed relational database.
*   **Supervisor Calibration:** Provide a supervisor review interface to confirm or override AI predictions while permanently preserving original model telemetry.
*   **Administrative Oversight:** Offer a product registry, component specification tracking (`P-PLATE01`), and an engineer inspection gallery with real-time summary statistics.
*   **Role-Based Access Control (RBAC):** Enforce strict role boundaries across Administrator, Engineer, and Supervisor users at both frontend and backend levels.

---

## 4. Technology Stack

| Category | Technology | Purpose | Implementation Status |
| :--- | :--- | :--- | :--- |
| **Frontend Framework** | React 18.3.1 | Component-based reactive UI | Implemented |
| **Frontend Tooling** | Vite 6.0.1 | Build tool and local development server | Implemented |
| **Routing** | React Router DOM 6.28.0 | Client-side routing and protected navigation | Implemented |
| **UI & Styling** | Bootstrap 5.3.3 + Custom CSS | Responsive layout grid and industrial UI styling | Implemented |
| **Icons** | Lucide React 0.468.0 | UI iconography and state indicators | Implemented |
| **HTTP Client** | Axios 1.7.9 | API communication with JWT interceptors | Implemented |
| **Backend Framework** | Django 5.2.18 | Web framework and ORM persistence | Implemented |
| **REST API** | Django REST Framework 3.18.3 | Serializers, API views, and permission enforcement | Implemented |
| **Authentication** | SimpleJWT 5.5.1 | JSON Web Token (JWT) authentication | Implemented |
| **AI / Computer Vision** | `BIT-PLATE-CV-1.0` (Pure Python) | Binary header parsing, entropy, gradient variance | Implemented |
| **Database** | SQLite 3 / PostgreSQL 18 (`psycopg 3.3.6`) | Relational persistence for products and inspections | Implemented |
| **Batch Processing** | Synchronous Execution | Sequential batch execution with fault isolation | Implemented |
| **Media Storage** | Django Media Storage (`FileField`) | Inspected image storage partitioned by year/month | Implemented |
| **Testing** | Django APITestCase | Automated unit tests for endpoints and RBAC | Implemented |

> [!NOTE]
> **Batch Architecture Clarification:** Batch image processing is implemented **synchronously** within the request lifecycle. Celery and Redis are not configured or running in this deployment. The API evaluates batch images sequentially, isolates individual file errors, and returns a consolidated response once all submitted images have been evaluated.

---

## 5. System Architecture

The Round 2 architecture comprises three integrated layers: the React frontend, the Django REST Framework API, and the `BIT-PLATE-CV-1.0` computer vision classifier.

```mermaid
flowchart TD
    subgraph Frontend["Frontend Client (React 18 + Vite)"]
        UI_Admin["Admin: Product Registry & Image Gallery"]
        UI_Eng["Engineer: Single & Batch Inspection"]
        UI_Sup["Supervisor: Inspection Review Queue"]
        AxiosClient["Axios HTTP Client (JWT Interceptor)"]
        
        UI_Admin --> AxiosClient
        UI_Eng --> AxiosClient
        UI_Sup --> AxiosClient
    end

    subgraph Backend["Backend API Layer (Django 5 + DRF)"]
        AuthMiddleware["JWT Authentication & RBAC Permissions"]
        Router["Django URL Dispatcher (/api/inspections/, /api/products/)"]
        Views["API Views (Single, Batch, History, Review)"]
        Serializer["DRF Serializers & Validation"]

        AxiosClient -->|"HTTP POST/GET (multipart/form-data & JSON)"| AuthMiddleware
        AuthMiddleware --> Router
        Router --> Views
        Views --> Serializer
    end

    subgraph AI_Engine["Inference Module (BIT-PLATE-CV-1.0)"]
        HeaderParser["Binary Header Parser (struct: PNG IHDR / JPEG SOF)"]
        EntropyCalc["Shannon Byte Entropy Calculator"]
        GradientVar["Spatial Gradient Variance Analyzer"]
        ProbabilitySigmoid["Defect Sigmoid Probability Mapper"]

        Views -->|"Raw Bytes"| HeaderParser
        HeaderParser --> EntropyCalc
        EntropyCalc --> GradientVar
        GradientVar --> ProbabilitySigmoid
        ProbabilitySigmoid -->|"Prediction Telemetry"| Views
    end

    subgraph Storage["Persistence Layer"]
        DB[(Relational DB: SQLite / PostgreSQL)]
        MediaDisk["Media Storage (/media/inspections/%Y/%m/)"]

        Views -->|"Product & Inspection Records"| DB
        Views -->|"Raw Image Files"| MediaDisk
    end
```

### Architecture Highlights

1.  **Stateless API Security:** API requests authenticate via short-lived JWT access tokens in the `Authorization: Bearer <token>` header. Expired tokens are refreshed transparently by Axios interceptors using the `/api/auth/refresh/` endpoint.
2.  **Pure-Python Computer Vision Engine:** The classifier parses binary image headers directly via Python's standard `struct` library, validating formats and dimensions without external C-extensions.
3.  **Sequential Fault-Isolated Batching:** Batch requests loop through uploaded files sequentially. If a file fails validation or contains corrupt data, it is recorded as `Failed` with an error message, while all valid images in the batch are processed and stored.
4.  **Non-Destructive Supervisor Overrides:** The database preserves original AI predictions (`predicted_class`, `confidence`, `defect_probability`) unconditionally. Supervisor review decisions are recorded in separate audit fields (`supervisor_class`, `supervisor_name`, `review_comment`, `reviewed_at`).

---

## 6. Main Application Modules

### A. Administrator Module

The Administrator Portal focuses on product configuration, quality monitoring, and inspection history:

*   **Product Registry (`/admin/products`):** Manage manufactured products. Default component `P-PLATE01` (*Industrial Metal Base Plate*) is registered with its active computer vision model (`BIT-PLATE-CV-1.0`) and category (*Milled Components*).
*   **Product Specifications:** Displays supported dimensional tolerances ($64 \times 64\text{ px}$ to $4096 \times 4096\text{ px}$), maximum file size ($5\text{ MiB}$), and supported file formats (JPEG, PNG).
*   **Engineer Inspection Image Gallery (`/admin/products/:productId`):** Centralized gallery displaying all inspection images uploaded by engineers for that specific product.
*   **Gallery Cards & Indicators:** Each inspection card displays the uploaded thumbnail, unique inspection ID, AI predicted class badge (`Normal` in green, `Defective` in red), confidence percentage, submitting engineer name, and timestamp.
*   **Summary Statistics:** Displays metrics calculated from backend inspection records:
    *   Total Inspections Run
    *   Total Normal Predictions
    *   Total Defective Predictions
    *   Pending vs. Completed Supervisor Reviews
*   **Inspection Detail Modal:** Clicking any gallery card opens an expanded image preview with full dimensional metadata, file size, defect probability, and supervisor review audit details.

### B. Engineer Module

The Engineer Portal provides quality inspection tools for factory floor operations:

*   **Product Selection:** Selects active target components (`P-PLATE01`) from the registered product catalog.
*   **Single-Image Inspection (`/engineer/quality-inspection`):**
    *   Interactive drag-and-drop zone with instant local client preview.
    *   Client-side pre-flight checks enforcing format, file size, and dimension constraints.
    *   One-click submission sending image and product ID to `POST /api/inspections/single/`.
    *   Result display showing predicted class, confidence percentage, defect probability, model version, and inspection ID.
*   **Batch-Image Inspection (`/engineer/batch-inspection`):**
    *   Supports dragging and dropping 1 to 10 images.
    *   Sequential addition: Dropping additional images appends them to the queue without clearing previously selected files.
    *   Per-image thumbnail grid with individual removal buttons.
    *   Batch submission reporting total items, completed items, and failed items.
*   **Personal Inspection History (`/engineer/inspection-history`):**
    *   Displays inspection records submitted by the logged-in engineer.
    *   Search by inspection ID or filename.
    *   Filter by predicted class (`All`, `Normal`, `Defective`), review status, or date.
    *   Detail view displaying original AI prediction and supervisor audit decisions.

### C. Supervisor Module

The Supervisor Portal enables quality supervisors to audit automated AI classifications:

*   **Inspection Review Queue (`/supervisor/inspection-review`):**
    *   Lists completed inspections across all plant engineers.
    *   Filter by review status (`Pending Review`, `Confirmed`, `Corrected`), predicted class, date, or engineer name.
*   **Inspection Review Modal:**
    *   High-resolution preview of the uploaded plate image.
    *   Displays original AI prediction, confidence score, and defect probability.
*   **Dual-Action Calibration Controls:**
    1.  **Confirm Prediction:** Confirms the AI classification. Updates `review_status` to `confirmed` and records `supervisor_class` equal to the original AI class.
    2.  **Correct Prediction:** Overrides the automated classification. Updates `review_status` to `corrected` and sets `supervisor_class` to the human-selected verdict (`Normal` or `Defective`).
*   **Audit Rationale & Identification:** Captures supervisor notes (e.g., *"Surface shadow mistaken for crack"*), automatically attaching supervisor name and timestamp.
*   **Audit Integrity:** Guarantees that original AI outputs remain immutable in the database.

---

## 7. AI Model and Prediction Workflow

### Model Architecture and Implementation

*   **Model Identifier:** `BIT-PLATE-CV-1.0`
*   **Source File:** `backend/inspections/classifier.py`
*   **Implementation Class:** `PlateQualityClassifier`
*   **Approach:** Deterministic computer vision feature extractor analyzing binary byte entropy and spatial scanline gradient variance.

> [!IMPORTANT]
> **Model Asset Verification Note:** Challenge reference files such as standalone `inference.py`, `classifier.npz`, or `model_metadata.json` are **not present** in this repository. All inference logic is contained directly in `backend/inspections/classifier.py`. The system does not claim deep learning training, external pre-trained weights, or GPU acceleration; it runs a deterministic feature-extraction pipeline in pure Python.

### Prediction Pipeline

```mermaid
sequenceDiagram
    autonumber
    actor Engineer as Quality Engineer
    participant API as Django View (inspections/views.py)
    participant Classifier as PlateQualityClassifier (classifier.py)
    participant DB as SQLite / PostgreSQL

    Engineer->>API: POST /api/inspections/single/ (image, product_id)
    API->>Classifier: validate_image_bytes(data)
    Note over Classifier: Checks magic bytes, PNG IHDR / JPEG SOF markers,<br/>verifies size <= 5MB, dimensions 64-4096 px
    API->>Classifier: predict(image_bytes)
    Note over Classifier: 1. Shannon byte entropy calculation<br/>2. Scanline gradient variance analysis<br/>3. Sigmoid defect probability mapping
    Classifier-->>API: {predicted_class, confidence, defect_probability, telemetry}
    API->>DB: Save InspectionRecord & write image to media
    DB-->>API: Record persisted (ID, timestamps)
    API-->>Engineer: HTTP 201 Created (Inspection JSON)
```

### Mathematical & Algorithmic Formulation

1.  **Binary Header Structural Parsing:**
    *   **PNG:** Validates `\x89PNG\r\n\x1a\n` header; decodes big-endian integers at byte offsets 16 and 20 within the `IHDR` chunk to extract width and height.
    *   **JPEG:** Validates `\xff\xd8` SOI; traverses segment markers to locate Start-of-Frame markers (`\xff\xc0`, `\xff\xc1`, `\xff\xc2`) to extract baseline bit precision, height, and width.
2.  **Shannon Byte Entropy Calculation:**
    Computes byte frequency distribution across sampled scanlines:
    $$H(X) = -\sum_{i=0}^{255} P(x_i) \log_2 P(x_i)$$
    Uniform metallic plate surfaces exhibit high entropy ($H(X) \approx 7.2 - 7.8$). Lower entropy indicates structural voids or density variations.
3.  **Luminance Gradient Variance:**
    Surface transitions are measured by calculating absolute adjacent differences across scanlines:
    $$\Delta_i = |x_i - x_{i-1}|, \quad \mu_\Delta = \frac{1}{N}\sum \Delta_i, \quad \sigma_\Delta^2 = \frac{1}{N}\sum (\Delta_i - \mu_\Delta)^2$$
    High localized gradient variance ($\sigma_\Delta^2$) signals sharp physical discontinuities such as burrs, cracks, or pitting.
4.  **Sigmoid Defect Probability Mapping:**
    Anomaly metrics combine variance and entropy factors:
    $$\text{Anomaly} = 0.70 \cdot \left(\frac{\sigma_\Delta^2}{2500}\right) + 0.30 \cdot \left(\frac{|H(X) - 7.5|}{3.0}\right)$$
    Defect probability ($P_\text{defect}$) is mapped through a logistic sigmoid bounded within $[0.012, 0.988]$:
    $$P_\text{defect} = \frac{1}{1 + e^{-6.0 \cdot (\text{Anomaly} - 0.45)}}$$
5.  **Decision Threshold:**
    $$\text{Class} = \begin{cases} \text{Defective}, & \text{if } P_\text{defect} \ge 0.50 \\ \text{Normal}, & \text{if } P_\text{defect} < 0.50 \end{cases}$$
    $$\text{Confidence} = \begin{cases} P_\text{defect}, & \text{if Defective} \\ 1.0 - P_\text{defect}, & \text{if Normal} \end{cases}$$

---

## 8. Image Upload and Validation

Validation is enforced across both client and server:

| Constraint | Backend Validation | Frontend Validation | Enforcement Mechanism |
| :--- | :--- | :--- | :--- |
| **Supported Formats** | JPEG (`.jpg`, `.jpeg`), PNG (`.png`) | JPEG (`.jpg`, `.jpeg`), PNG (`.png`) | Binary magic byte inspection (`parse_image_dimensions`) & MIME verification |
| **Maximum File Size** | $5\text{ MiB}$ ($5,242,880\text{ bytes}$) | $5\text{ MiB}$ ($5,242,880\text{ bytes}$) | Raw byte length checks before processing |
| **Minimum Dimensions**| $64 \times 64\text{ pixels}$ | $64 \times 64\text{ pixels}$ | Decoded header resolution / DOM `Image.naturalWidth` |
| **Maximum Dimensions**| $4096 \times 4096\text{ pixels}$ | $4096 \times 4096\text{ pixels}$ | Decoded header resolution / DOM `Image.naturalHeight` |
| **Batch Size** | 1 to 10 images | 1 to 10 images | Request files array length validation |
| **Empty File Detection**| Rejects 0-byte uploads | Rejects 0-byte uploads | Size verification |
| **Corrupted Files** | Raises `ImageValidationError` (400) | Triggers client error alert | Catches incomplete byte streams or missing frame markers |

---

## 9. Complete Application Workflow

```mermaid
flowchart TD
    Start([User Arrives]) --> Login[Authenticate via /api/auth/login/]
    Login --> RoleCheck{Role Check}

    RoleCheck -->|Admin| AdminPortal[Admin: Product Registry /admin/products]
    RoleCheck -->|Engineer| EngPortal[Engineer: Quality Inspection /engineer/quality-inspection]
    RoleCheck -->|Supervisor| SupPortal[Supervisor: Review Queue /supervisor/inspection-review]

    EngPortal --> ChooseMode{Inspection Type}
    ChooseMode -->|Single| SingleFlow[Upload 1 Image via /api/inspections/single/]
    ChooseMode -->|Batch| BatchFlow[Upload 1-10 Images via /api/inspections/batch/]

    SingleFlow --> Validate{Validation Check}
    BatchFlow --> Validate

    Validate -->|Pass| Infer[BIT-PLATE-CV-1.0 Inference]
    Validate -->|Fail| ReturnErr[HTTP 400 Bad Request / Item Error]

    Infer --> SaveDB[Persist InspectionRecord in Database]
    SaveDB --> ShowResult[Display Prediction & Confidence Score]

    ShowResult --> SupQueue[Record Queued for Supervisor Review]
    SupQueue --> SupPortal
    
    SupPortal --> Decision{Supervisor Action}
    Decision -->|Confirm| ConfirmAction[Mark Confirmed: supervisor_class = predicted_class]
    Decision -->|Correct| OverrideAction[Mark Corrected: supervisor_class = Override Value]

    ConfirmAction --> AuditSaved[(Audit Trail Stored in Database)]
    OverrideAction --> AuditSaved

    AuditSaved --> AdminView[Admin Reviews Gallery & Updated Statistics]
```

---

## 10. Role-Based Access Control (RBAC)

The system enforces multi-tiered security across frontend route guards and backend permissions:

| Role | Frontend Access Scope | Backend Permissions | Data Access Scope |
| :--- | :--- | :--- | :--- |
| **Administrator** (`ADMIN`) | Product Registry, Product Details, Inspection Gallery, Plant Admin Overview | `IsAdmin`, `IsAuthenticated` | Unrestricted read/write access to all products and inspection records across all engineers. |
| **Engineer** (`ENGINEER`) | Single Quality Inspection, Batch Inspection, Personal Inspection History | `IsAuthenticated` (scoped in views) | Read/write access to create inspections; read access restricted **strictly to own submitted records**. |
| **Supervisor** (`SUPERVISOR`)| Inspection Review Queue, Inspection Detail & Calibration Modal | `IsSupervisor`, `IsAuthenticated` | Read access to all completed inspection records; exclusive write access to confirm or correct predictions. |

> [!IMPORTANT]
> Frontend route protections in `ProtectedRoute.jsx` manage navigation display, while backend views strictly enforce data scoping (e.g. `queryset.filter(user=request.user)` for Engineers) and permission classes (`IsAdmin`, `IsSupervisor`).

---

## 11. Database Design

```mermaid
erDiagram
    User ||--o{ InspectionRecord : "submits (user_id)"
    User ||--o{ BatchInspection : "initiates (user_id)"
    User ||--o{ InspectionRecord : "reviews (supervisor_id)"
    Product ||--o{ InspectionRecord : "categorizes (product_id)"

    Product {
        string id PK "Unique Product ID (e.g. P-PLATE01)"
        string name "Product Name"
        string model_version "Target CV Model"
        string category "Component Category"
        text description "Component Description"
        string status "Status (Active/Inactive)"
        string min_dimensions "Min Dimension constraint"
        string max_dimensions "Max Dimension constraint"
        datetime created_at "Registration Timestamp"
        datetime updated_at "Update Timestamp"
    }

    BatchInspection {
        string batch_id PK "Unique Batch Identifier"
        string product_id "Target Product ID"
        int total_images "Total images submitted"
        int completed_count "Successfully processed count"
        int failed_count "Failed items count"
        string status "Batch Status (Completed/Processing)"
        datetime created_at "Creation Timestamp"
        datetime updated_at "Update Timestamp"
    }

    InspectionRecord {
        bigint id PK "Auto-increment primary key"
        string product_id FK "References Product.id"
        bigint user_id FK "Submitting Engineer"
        string engineer_name "Engineer display name"
        string image "Relative media file path"
        string file_name "Original uploaded filename"
        bigint file_size "File size in bytes"
        int image_width "Pixel width"
        int image_height "Pixel height"
        string predicted_class "Normal or Defective (Original AI)"
        float confidence "Model confidence (0.0 to 1.0)"
        float defect_probability "Defect probability score"
        string model_version "Classifier version string"
        string status "Queued / Processing / Completed / Failed"
        text error_message "Error telemetry if failed"
        string review_status "pending / confirmed / corrected"
        string supervisor_class "Supervisor decision class"
        bigint supervisor_id FK "Reviewing Supervisor"
        string supervisor_name "Supervisor display name"
        text review_comment "Audit rationale comment"
        datetime reviewed_at "Audit timestamp"
        string batch_id "Associated batch ID if bulk"
        datetime created_at "Submission timestamp"
        datetime updated_at "Record update timestamp"
    }

    User {
        bigint id PK "Auto-increment primary key"
        string email UK "Email (Sole Auth Identifier)"
        string first_name "First name"
        string last_name "Last name"
        string role "ADMIN / ENGINEER / SUPERVISOR"
        boolean is_active "Active status"
    }
```

---

## 12. API Documentation

### Endpoint Summary Table

| HTTP Method | API Endpoint | Description | Access Role |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/products/` | List all registered inspection products | Authenticated |
| `POST` | `/api/products/` | Register a new manufactured product | Admin Only |
| `GET` | `/api/products/<str:pk>/` | Retrieve specifications of a specific product | Authenticated |
| `GET` | `/api/inspections/` | List inspection records with query filters | Role Scoped |
| `POST` | `/api/inspections/single/` | Upload single plate image for AI quality classification | Engineer, Admin, Supervisor |
| `POST` | `/api/inspections/` | Standard alias for single inspection upload | Engineer, Admin, Supervisor |
| `POST` | `/api/inspections/batch/` | Upload 1–10 plate images for sequential batch inference | Engineer, Admin, Supervisor |
| `GET` | `/api/inspections/batch/<str:batch_id>/` | Retrieve batch execution state and item results | Authenticated |
| `GET` | `/api/inspections/<int:pk>/` | Retrieve detailed inspection record by primary key | Authenticated |
| `POST` | `/api/inspections/<int:pk>/review/` | Submit supervisor review action (confirm or correct) | Supervisor, Admin |
| `GET` | `/api/supervisor/inspections/` | Retrieve inspection queue for supervisor review | Supervisor, Admin |
| `POST` | `/api/supervisor/inspections/<int:pk>/review/` | Direct alias for supervisor review action | Supervisor, Admin |
| `GET` | `/api/health/` | System health status and database connectivity probe | Public |

---

### Detailed Endpoint Specifications

#### 1. List Products
*   **Path:** `GET /api/products/`
*   **Access:** Authenticated (All Roles)
*   **Illustrative Example Response (200 OK):**
    ```json
    [
      {
        "id": "P-PLATE01",
        "name": "Industrial Metal Base Plate",
        "model_version": "BIT-PLATE-CV-1.0",
        "category": "Milled Components",
        "description": "Precision milled metallic mounting plate inspected for surface cracks, porosities, and machining defects.",
        "status": "Active",
        "min_dimensions": "64x64",
        "max_dimensions": "4096x4096",
        "created_at": "2026-11-03T02:44:00Z",
        "updated_at": "2026-11-03T02:44:00Z"
      }
    ]
    ```

#### 2. Single Image Inspection Upload
*   **Path:** `POST /api/inspections/single/` (or `POST /api/inspections/`)
*   **Content-Type:** `multipart/form-data`
*   **Parameters:**
    *   `file` (File, Required): JPEG or PNG image binary.
    *   `product_id` (String, Optional): Target product ID (Defaults to `"P-PLATE01"`).
*   **Illustrative Example Response (201 Created):**
    ```json
    {
      "id": 14,
      "product_id": "P-PLATE01",
      "image_url": "http://localhost:8000/media/inspections/2026/11/plate_sample.png",
      "thumbnail_url": "http://localhost:8000/media/inspections/2026/11/plate_sample.png",
      "predicted_class": "Normal",
      "confidence": 0.9824,
      "defect_probability": 0.0176,
      "model_version": "BIT-PLATE-CV-1.0",
      "status": "Completed",
      "error_message": "",
      "review_status": "pending",
      "supervisor_class": "",
      "supervisor_name": "",
      "review_comment": "",
      "reviewed_at": null,
      "engineer_name": "John Engineer",
      "file_name": "plate_sample.png",
      "file_size": 245120,
      "image_width": 1024,
      "image_height": 1024,
      "batch_id": "",
      "created_at": "2026-11-03T02:46:12Z",
      "updated_at": "2026-11-03T02:46:12Z"
    }
    ```

#### 3. Batch Image Inspection Upload
*   **Path:** `POST /api/inspections/batch/`
*   **Content-Type:** `multipart/form-data`
*   **Parameters:**
    *   `files` or `images` (File[], Required): Array of 1 to 10 image files.
    *   `product_id` (String, Optional): Target product ID.
*   **Illustrative Example Response (201 Created):**
    ```json
    {
      "batch_id": "BATCH-20261103024800-A1B2C3",
      "total": 2,
      "completed": 2,
      "failed": 0,
      "items": [
        {
          "id": 15,
          "product_id": "P-PLATE01",
          "image_url": "http://localhost:8000/media/inspections/2026/11/img1.png",
          "predicted_class": "Normal",
          "confidence": 0.9750,
          "defect_probability": 0.0250,
          "status": "Completed"
        },
        {
          "id": 16,
          "product_id": "P-PLATE01",
          "image_url": "http://localhost:8000/media/inspections/2026/11/img2.png",
          "predicted_class": "Defective",
          "confidence": 0.9412,
          "defect_probability": 0.9412,
          "status": "Completed"
        }
      ]
    }
    ```

#### 4. Filtered Inspections Query (Admin Gallery & History)
*   **Path:** `GET /api/inspections/`
*   **Query Parameters:**
    *   `product_id`: Scopes records to specific product (e.g. `?product_id=P-PLATE01`).
    *   `predicted_class`: Filters by predicted class (`all`, `Normal`, `Defective`).
    *   `review_status`: Filters by review state (`all`, `pending`, `confirmed`, `corrected`).
    *   `search`: Keyword search matching inspection ID, engineer name, or filename.
    *   `date`: Filter by date (`YYYY-MM-DD`).
*   **Access Scoping:** Admins/Supervisors see all records; Engineers see only their own uploads.

#### 5. Supervisor Review Action
*   **Path:** `POST /api/inspections/<int:pk>/review/`
*   **Access:** Supervisor or Admin Only
*   **Request Body (JSON):**
    ```json
    {
      "action": "correct",
      "corrected_class": "Normal",
      "comment": "Surface shadow was mistaken for crack; dimensional tolerance verified."
    }
    ```
*   **Illustrative Example Response (200 OK):**
    ```json
    {
      "id": 16,
      "product_id": "P-PLATE01",
      "predicted_class": "Defective",
      "confidence": 0.9412,
      "review_status": "corrected",
      "supervisor_class": "Normal",
      "supervisor_name": "Jane Supervisor",
      "review_comment": "Surface shadow was mistaken for crack; dimensional tolerance verified.",
      "reviewed_at": "2026-11-03T02:49:00Z"
    }
    ```

---

## 13. Frontend Project Structure

```text
frontend/src/
├── App.jsx                                  # Root router and role-based route guards
├── main.jsx                                 # Application entry point mounting React 18 DOM
├── components/
│   ├── auth/
│   │   └── ProtectedRoute.jsx               # RBAC route guard enforcing allowed roles
│   ├── common/
│   │   ├── EmptyState.jsx                   # Placeholder for zero-result states
│   │   ├── LoadingSpinner.jsx               # Loading spinner indicator
│   │   ├── Navbar.jsx                       # Top navigation bar with active user profile
│   │   ├── Sidebar.jsx                      # Navigation sidebar with role-aware portal links
│   │   └── StatusBadge.jsx                  # Standard status badge component
│   └── inspection/
│       ├── BatchProgress.jsx                # Progress bar for batch upload states
│       ├── ImageUploader.jsx                # Drag-and-drop file uploader with validation
│       ├── InspectionResultCard.jsx         # Card displaying prediction, confidence, and telemetry
│       ├── InspectionStatusBadge.jsx        # Badges for Normal, Defective, and Review states
│       └── ProductInspectionGallery.jsx     # Admin inspection gallery for product details
├── context/
│   └── AuthContext.jsx                      # JWT state provider (login, token refresh, logout)
├── hooks/
│   └── useAuth.js                           # Custom hook exposing authentication state
├── layouts/
│   ├── AuthLayout.jsx                       # Container layout for login screen
│   └── MainLayout.jsx                       # Main shell containing Navbar, Sidebar, and content
├── pages/
│   ├── admin/
│   │   ├── AdminDashboard.jsx               # Plant administration overview
│   │   └── ProductsPage.jsx                 # Product Registry & Inspection Image Gallery
│   ├── auth/
│   │   └── LoginPage.jsx                    # Login page with demo role credentials
│   ├── common/
│   │   ├── NotFoundPage.jsx                 # HTTP 404 page
│   │   └── UnauthorizedPage.jsx             # HTTP 403 page
│   ├── engineer/
│   │   ├── BatchInspectionPage.jsx          # 1-10 image batch inspection page
│   │   ├── InspectionHistoryPage.jsx        # Personal inspection history page
│   │   └── QualityInspectionPage.jsx        # Single-image quality inspection page
│   └── supervisor/
│       ├── InspectionDetailModal.jsx        # Modal for confirming/correcting AI predictions
│       └── InspectionReviewPage.jsx         # Supervisor inspection review queue
├── services/
│   ├── api.js                               # Axios client with JWT request/response interceptors
│   ├── authService.js                       # Login, refresh, and profile retrieval services
│   ├── inspectionService.js                 # Centralized Visual Quality Inspection API client
│   └── mockData.js                          # Static fallbacks for offline testing
├── styles/
│   └── index.css                            # Global application styles and overrides
└── utils/
    ├── constants.js                         # Application-wide constants
    ├── errorHandler.js                      # Error message extraction
    ├── formatters.js                        # Date, time, and file size formatters
    ├── imageValidators.js                   # Client-side format, size, and dimension checks
    └── roleUtils.js                         # Role normalization and display utilities
```

---

## 14. Backend Project Structure

```text
backend/
├── manage.py                                # Django CLI management entry point
├── requirements.txt                         # Python runtime dependencies
├── db.sqlite3                               # Development SQLite database instance
├── config/
│   ├── asgi.py                              # ASGI entry point
│   ├── settings.py                          # Core configuration, installed apps, and media settings
│   ├── urls.py                              # Root URL dispatcher registering all API namespaces
│   ├── views.py                             # HealthCheckView (/api/health/)
│   └── wsgi.py                              # WSGI deployment entry point
├── accounts/
│   ├── managers.py                          # Custom UserManager for email-based authentication
│   ├── models.py                            # Custom User model and UserRole enum
│   ├── permissions.py                       # RBAC permissions (IsAdmin, IsSupervisor, IsEngineer)
│   ├── serializers.py                       # User and Token serializers
│   ├── tests.py                             # Auth and permission unit tests
│   ├── urls.py                              # Authentication URLs (/api/auth/login/, /refresh/)
│   └── views.py                             # Login, token refresh, and user profile views
├── inspections/
│   ├── apps.py                              # InspectionsConfig application registry
│   ├── classifier.py                        # BIT-PLATE-CV-1.0 CV engine & binary header parser
│   ├── models.py                            # Product, BatchInspection, and InspectionRecord models
│   ├── product_urls.py                      # Sub-routing for /api/products/
│   ├── serializers.py                       # Serializers for products, inspections, and reviews
│   ├── tests.py                             # Unit tests for inspection endpoints and RBAC
│   ├── urls.py                              # Sub-routing for /api/inspections/
│   ├── views.py                             # API views for single, batch, product, and review
│   └── migrations/
│       └── 0001_initial.py                  # Schema migration for inspection models
└── media/                                   # Uploaded media storage root
    └── inspections/                         # Inspected images organized by year and month
        └── 2026/11/
```

---

## 15. Installation and Setup

### Prerequisites

*   **Python:** Version `3.10`, `3.11`, or `3.12` installed.
*   **Node.js:** Version `18.x` or `20.x` LTS installed.
*   **npm:** Version `9.x` or `10.x` installed.

---

### Backend Setup

1.  **Navigate to backend directory:**
    ```bash
    cd backend
    ```

2.  **Create and activate virtual environment:**
    *   **Windows (PowerShell):**
        ```powershell
        python -m venv .venv
        .venv\Scripts\Activate.ps1
        ```
    *   **Linux / macOS:**
        ```bash
        python3 -m venv .venv
        source .venv/bin/activate
        ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure environment variables:**
    Create a `.env` file in the `backend/` directory:
    ```dotenv
    SECRET_KEY=your-secure-development-secret-key-placeholder
    DEBUG=True
    ALLOWED_HOSTS=127.0.0.1,localhost
    USE_SQLITE=True
    CORS_ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
    ```

5.  **Apply database migrations:**
    ```bash
    python manage.py migrate
    ```

---

### Frontend Setup

1.  **Navigate to frontend directory:**
    ```bash
    cd ../frontend
    ```

2.  **Install npm packages:**
    ```bash
    npm install
    ```

3.  **Configure frontend environment variables:**
    Ensure `frontend/.env` is configured:
    ```dotenv
    VITE_API_BASE_URL=http://localhost:8000/api
    VITE_USE_MOCK_FALLBACK=false
    ```

---

### AI Model Setup

The `BIT-PLATE-CV-1.0` computer vision classifier is implemented in `backend/inspections/classifier.py`. It requires no external model download, pre-trained weights file, or third-party computer vision libraries. It loads directly when the Django server starts.

---

## 16. How to Run the Application

Run the application using two separate terminals.

### Terminal 1: Backend Server

```bash
cd backend
# Windows:
.venv\Scripts\Activate.ps1
# Linux / macOS: source .venv/bin/activate

python manage.py runserver 8000
```
*   **Backend URL:** `http://localhost:8000`
*   **Health Probe:** `http://localhost:8000/api/health/`
*   **Django Admin:** `http://localhost:8000/admin/`

---

### Terminal 2: Frontend Client

```bash
cd frontend
npm run dev
```
*   **Frontend Application URL:** `http://localhost:5173`

---

## 17. Testing and Model Evaluation

### Automated Test Suites

The project includes unit tests covering inspection endpoints, product filtering, batch processing, and supervisor reviews.

1.  **Run Inspections App Tests:**
    ```bash
    cd backend
    python manage.py test inspections
    ```
    *Output:*
    ```text
    Creating test database for alias 'default'...
    ........
    ----------------------------------------------------------------------
    Ran 8 tests in 10.238s

    OK
    Destroying test database for alias 'default'...
    ```

2.  **Run All Backend Test Suites:**
    ```bash
    python manage.py test accounts machines documents history rag inspections
    ```
    *Output:*
    ```text
    Ran 67 tests in 47.355s — OK (0 failures, 0 errors)
    ```

3.  **Verify Frontend Production Build:**
    ```bash
    cd frontend
    npm run build
    ```
    *Output:*
    ```text
    ✓ 1846 modules transformed.
    dist/index.html                   0.76 kB
    dist/assets/index-De9MYNw1.css  234.52 kB
    dist/assets/index-D8GzofCw.js   572.12 kB
    ✓ built in 5.64s
    ```

---

### Tested Scenarios

*   `test_products_list_endpoint`: Verifies `GET /api/products/` returns `P-PLATE01`.
*   `test_single_inspection_upload`: Verifies `POST /api/inspections/single/` uploads a valid image, invokes the classifier, and returns valid prediction telemetry.
*   `test_single_inspection_invalid_format_rejected`: Validates rejection of non-image files with HTTP 400.
*   `test_inspections_product_filter`: Confirms that `GET /api/inspections/?product_id=P-PLATE01` returns only records belonging to the queried product.
*   `test_batch_inspection_upload`: Verifies uploading multiple files returns a valid batch summary and individual results.
*   `test_supervisor_review_confirm_action`: Tests that a supervisor confirming an inspection sets `review_status = 'confirmed'` and records supervisor identity without altering the original AI class.
*   `test_supervisor_review_correct_action`: Tests that a supervisor correcting an inspection updates `supervisor_class` to the human verdict while leaving `predicted_class` unchanged.
*   `test_engineer_cannot_submit_supervisor_review`: Verifies that unauthorized users (Engineers) receive HTTP 403 Forbidden when attempting to submit reviews.

---

### Model Evaluation & Dataset Performance Notes

*   **Sample Dataset Performance:** When evaluated on sample metal base plate images, `BIT-PLATE-CV-1.0` distinguishes uniform, high-entropy plates (`Normal`) from plates containing localized surface gradient spikes (`Defective`).
*   **No Benchmark Script in Repository:** Note that a standalone 60-image labeled evaluation script or benchmark harness is not bundled in this repository. Model behavior has been verified via unit tests using synthetic and sample images conforming to challenge constraints.
*   **Production Caveats:** Real-world manufacturing environments feature variable lighting, oil residues, and vibrational noise. While the deterministic heuristic achieves consistent classification on controlled sample images, industrial deployment requires training deep neural networks on factory-line datasets.

---

## 18. Error Handling and Security

### Security Architecture

1.  **Authentication & Stateless Tokens:** SimpleJWT issues short-lived access tokens ($60\text{ minutes}$) and refresh tokens. Password hashes use PBKDF2 with SHA-256.
2.  **Role Enforcement:** Role permissions (`IsAdmin`, `IsSupervisor`, `IsEngineer`) are checked on every API call. Engineers cannot view records belonging to other technicians, and cannot submit supervisor review actions.
3.  **Sanitized Input Handling:**
    *   File names are sanitized to prevent directory traversal.
    *   Image dimensions and formats are validated directly from binary headers to prevent MIME-spoofing.
4.  **CORS & Host Headers:** Cross-Origin Resource Sharing is locked to configured frontend origins (`http://localhost:5173`).

### Error Handling Strategy

*   **HTTP 400 Bad Request:** Returned for invalid file types, empty files, size violations ($>5\text{MB}$), resolution violations ($<64\text{px}$ or $>4096\text{px}$), or invalid review payloads.
*   **HTTP 401 Unauthorized:** Returned for missing, invalid, or expired tokens, triggering automatic token refresh or redirection to `/login`.
*   **HTTP 403 Forbidden:** Returned when an authenticated user attempts to access endpoints outside their role privileges.
*   **HTTP 404 Not Found:** Returned when querying non-existent product IDs, inspection records, or batch jobs.
*   **HTTP 500 Internal Server Error:** Unhandled server exceptions return generic error envelopes while preserving stack traces in server logs.

---

## 19. Limitations and Future Enhancements

### Current System Limitations

1.  **Single Active Product Focus:** The computer vision heuristic is tailored for `P-PLATE01` (*Industrial Metal Base Plates*). Additional component geometries require specific calibration thresholds.
2.  **Binary Defect Categorization:** Defective items are classified under the generic label `Defective` without fine-grained defect sub-categorization (such as distinguishing between a scratch, burr, or porosity).
3.  **Synchronous Batch Execution:** Batch processing runs sequentially within the HTTP request. While fault-isolated and fast for up to 10 images, enterprise scale (hundreds of images) would benefit from an asynchronous task queue (e.g., Celery + Redis).
4.  **No Spatial Bounding Boxes:** The system outputs classification predictions and confidence scores, but does not render localized bounding boxes or Grad-CAM heatmaps over the defect region.
5.  **External Model Asset Discrepancy:** The repository does not include external model files (`inference.py`, `classifier.npz`, `model_metadata.json`); inference relies on the built-in pure-Python `BIT-PLATE-CV-1.0` classifier.

### Proposed Future Enhancements

*   **Deep Learning Model Integration:** Integrate deep convolutional neural networks (e.g., YOLOv8, ResNet-50, or EfficientNet) for multi-class defect localization (pitting, scratches, burrs, cracks).
*   **Defect Heatmaps (Grad-CAM):** Overlay visual attention heatmaps on inspected images to highlight the exact pixel regions driving the model's defect classification.
*   **Edge Hardware Deployment:** Compile models for on-device inference using ONNX Runtime or TensorRT on industrial edge devices (such as NVIDIA Jetson) mounted above conveyor belts.
*   **Automated Retraining Loop:** Leverage supervisor corrections (`review_status = 'corrected'`) as active-learning training samples to retrain the model on edge cases.
*   **Asynchronous Task Queue:** Introduce Celery and Redis to handle concurrent large-scale batch processing beyond the current 10-image limit.

---

## 20. Conclusion

The **AI Visual Quality Inspection System for Manufacturing** provides an automated visual quality assurance platform for discrete manufacturing lines. By combining an in-memory Computer Vision inference engine with a dual-tier human-in-the-loop review architecture, the system delivers rapid defect identification while maintaining total audit transparency.

Through role-tailored workflows for Administrators, Quality Engineers, and Quality Supervisors, the platform eliminates inspection bottlenecks, prevents defective components from escaping to downstream assembly, and establishes a reliable foundation for continuous manufacturing intelligence.
