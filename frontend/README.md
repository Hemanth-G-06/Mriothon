# Manufacturing Manual Assistant – React Frontend

Role-based AI-powered industrial documentation assistant built with React, Vite, Bootstrap 5, Axios, Lucide Icons, and React Markdown.

---

## 🚀 Quick Start

### 1. Install Dependencies
```bash
cd frontend
npm install
```

### 2. Configure Environment
Create or edit `.env` in the `frontend/` root:
```ini
# Base URL for Django REST Framework APIs
VITE_API_BASE_URL=http://localhost:8000/api

# Automatically use mock fallback when backend server is offline/unreachable
VITE_USE_MOCK_FALLBACK=true
```

### 3. Start Development Server
```bash
npm run dev
```
Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## 👥 User Roles & Test Credentials

The frontend supports role-based views and navigation. For quick hackathon testing when the backend is offline, use the preset buttons on the Login page:

| Role | Username | Password | Permitted Features |
|---|---|---|---|
| **Admin** | `admin` | `admin123` | Equipment Registry, PDF Manual Upload, Vector Indexing Status |
| **Engineer** | `engineer` | `engineer123` | Machine Selector, RAG AI Assistant, Citation Chips, Page-jump PDF Viewer |
| **Supervisor** | `supervisor` | `supervisor123` | Read-only Question History, Accuracy Auditing, Search & Filters |

---

## 🔌 Django Backend Integration Guide

The frontend communicates with the backend via a centralized Axios client in `src/services/api.js`.

### Expected API Endpoints

#### Authentication & Profile
- `POST /api/auth/login/` → Body: `{ username, email, password }` Returns `{ access, refresh, user: { id, username, first_name, last_name, email, role, full_name } }`
- `POST /api/auth/register/` → Body: `{ first_name, last_name, email, password, password_confirm }` Returns `{ success: true, message: "..." }`
- `POST /api/auth/refresh/` → Body: `{ refresh }` Returns `{ access }`
- `POST /api/auth/logout/` → Body: `{ refresh }`
- `GET /api/auth/me/` → Returns current user profile with `{ id, username, first_name, last_name, email, role, full_name }` used for the top-right profile and dropdown

#### Equipment & Machines
- `GET /api/machines/` → Returns list of machines `[{ id, name, model_number, serial_number, description, location, manuals_count }]`
- `GET /api/machines/{id}/` → Returns machine details
- `POST /api/machines/` → Body: `{ name, model_number, serial_number, location, description }`

#### Documents & Manuals
- `GET /api/documents/` (optional `?machine_id={id}`) → Returns list of documents `[{ id, machine_id, machine_name, title, manual_type, model_number, revision, file_size, status, created_at }]`
- `POST /api/documents/upload/` → `multipart/form-data` with `file`, `machine_id`, `title`, `manual_type`, `model_number`, `revision`
- `GET /api/documents/{id}/pdf/` → Protected endpoint returning binary PDF stream (`application/pdf`) with JWT Authorization header

#### Engineer Chat & Citations
- `POST /api/chat/ask/` → Body: `{ machine_id, question }`
  Returns:
  ```json
  {
    "id": 101,
    "machine_id": 1,
    "question": "What is the warmup procedure?",
    "answer": "Execute cycle O9001...",
    "is_insufficient_evidence": false,
    "citations": [
      {
        "id": "cit-1",
        "document_id": 101,
        "document_title": "HP-200 Operations Manual",
        "revision": "Rev 2.4",
        "page_number": 34,
        "snippet": "Section 4.2 Spindle Warm-up Cycle..."
      }
    ],
    "created_at": "2025-04-10T10:14:00Z"
  }
  ```
- `GET /api/chat/history/?machine_id={id}` → Returns previous Q&A pairs for the selected machine

#### Supervisor Audit & History
- `GET /api/supervisor/history/?machine=&engineer=&date=&status=&search=` → Returns list of questions with answers and citations
- `GET /api/supervisor/history/{id}/` → Returns single question detail
- `GET /api/supervisor/statistics/` → Returns `{ total_questions, answered_questions, insufficient_evidence_questions, active_machines_monitored }`

---

## 📁 Architecture & File Structure

```
frontend/
├── index.html
├── vite.config.js
├── .env
├── src/
│   ├── components/
│   │   ├── auth/          # ProtectedRoute, role authorization guards
│   │   ├── chat/          # MachineSelector, ChatMessage, ChatInput, CitationCard
│   │   ├── common/        # Navbar, Sidebar, StatusBadge, LoadingSpinner, EmptyState
│   │   └── pdf/           # PdfViewerModal with page jump navigation
│   ├── context/           # AuthContext (JWT tokens, session storage)
│   ├── hooks/             # useAuth
│   ├── layouts/           # MainLayout (responsive sidebar & topbar), AuthLayout
│   ├── pages/
│   │   ├── admin/         # AdminDashboard, MachinesPage, DocumentsPage
│   │   ├── auth/          # LoginPage with show/hide password and quick presets
│   │   ├── common/        # NotFoundPage (404), UnauthorizedPage (403)
│   │   ├── engineer/      # EngineerDashboard (machine-specific RAG assistant)
│   │   └── supervisor/    # SupervisorDashboard, QuestionDetailModal
│   ├── services/          # Centralized api.js, authService, machineService, documentService, chatService, supervisorService, mockData
│   ├── styles/            # index.css (Industrial navy/slate theme, custom badges, bubbles)
│   ├── utils/             # constants.js, formatters.js
│   ├── App.jsx            # React Router v6 configuration & role redirection
│   └── main.jsx
```
