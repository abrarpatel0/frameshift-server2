# FrameShift Project Report
**Generated**: April 11, 2026

---

## Table of Contents
1. [Frontend Overview](#frontend-overview)
2. [Backend Overview](#backend-overview)
3. [Database Overview](#database-overview)
4. [System Architecture](#system-architecture)
5. [API Endpoints](#api-endpoints)
6. [Data Models](#data-models)
7. [Technology Stack](#technology-stack)

---

## Frontend Overview

### Framework & Architecture
- **Framework**: Next.js 16.1.7 (React Meta Framework)
- **Port**: 3001
- **Language**: JavaScript (React 19.2.4)
- **Build Tool**: Next.js built-in compiler
- **Styling**: Tailwind CSS v4

### Key Dependencies
| Package | Version | Purpose |
|---------|---------|---------|
| Next.js | ^16.1.7 | React framework for production |
| React | ^19.2.4 | UI library |
| Axios | ^1.13.2 | HTTP client for API requests |
| React Query | ^5.90.12 | Server state management |
| Zustand | ^5.0.9 | Client state management |
| React Hook Form | ^7.69.0 | Form state management |
| React Hot Toast | ^2.6.0 | Toast notifications |
| Framer Motion | ^12.23.26 | Animation library |
| React Syntax Highlighter | ^16.1.0 | Code syntax highlighting |
| Lucide React | ^0.562.0 | Icon library |

### Application Structure

```
frameshift_client/
├── app/
│   ├── auth/              # Authentication pages (sign-in, register)
│   ├── sign-in/           # Login page
│   ├── register/          # User registration
│   ├── forgot-password/   # Password recovery
│   ├── reset-password/    # Password reset
│   ├── verify-email/      # Email verification
│   ├── dashboard/         # User dashboard
│   ├── conversion/        # Project conversion interface
│   ├── reports/           # Conversion reports view
│   ├── admin/             # Admin panel
│   ├── settings/          # User settings
│   ├── migrations/        # Migration management
│   ├── new-migration/     # Create new migration
│   ├── layout.js          # Root layout
│   ├── page.js            # Landing page
│   ├── globals.css        # Global styles
│   └── providers.jsx      # Context providers
├── components/            # Reusable React components
│   ├── ui/                # UI components (GlassCard, etc.)
│   ├── admin/             # Admin-specific components
│   ├── conversion/        # Conversion components
│   ├── modals/            # Modal dialogs
│   ├── steps/             # Step indicators
│   ├── loaders/           # Loading states
│   ├── animations/        # Animation components
│   ├── Navbar.jsx         # Navigation bar
│   ├── Sidebar.jsx        # Side navigation
│   ├── Button.jsx         # Button component
│   ├── Input.jsx          # Input component
│   ├── FileTreeBrowser.jsx # File tree viewer
│   ├── CodeDiffViewer.jsx  # Diff viewer component
│   ├── ProgressSteps.jsx   # Progress indicator
│   └── ErrorDialog.jsx     # Error modal
├── hooks/                 # Custom React hooks
│   ├── useMediaQuery.js   # Responsive design hook
│   └── useUploadProgress.js # Progress tracking
├── lib/                   # Utility libraries
│   ├── api.js             # API configuration & requests
│   ├── websocket.js       # WebSocket client
│   ├── errorMessages.js   # Error message constants
│   ├── toast.js           # Toast utilities
│   └── runtimeConfig.js   # Runtime configuration
├── store/                 # Zustand state stores
│   ├── useAuthStore.js    # Authentication state
│   └── useConnectionStore.js # Connection status
├── utils/                 # Utility functions
│   ├── fileValidation.js  # File validation logic
│   └── formatting.js      # Data formatting
└── public/                # Static assets
```

### Key Frontend Features
- **Authentication**: Email/password and GitHub OAuth
- **Project Management**: Upload or GitHub source projects
- **Conversion Interface**: Step-by-step conversion workflow
- **Real-time Progress**: WebSocket-based progress updates
- **Code Diff Viewer**: Visual comparison of converted code
- **Conversion Reports**: Detailed migration reports
- **User Dashboard**: Project and job management
- **Admin Panel**: User management and statistics
- **Responsive Design**: Mobile-friendly UI

---

## Backend Overview

### Framework & Architecture
- **Runtime**: Node.js with Express.js 5.2.1 (API Server)
- **Backend Language**: Python 3.12+ (Conversion Engine)
- **Port**: 3000 (default)
- **Architecture**: Hybrid Node.js/Python monolith
- **Database**: PostgreSQL with SQLAlchemy ORM

### Node.js Dependencies (Express API)
| Package | Version | Purpose |
|---------|---------|---------|
| Express | ^5.2.1 | Web framework |
| PostgreSQL Driver (pg) | ^8.16.3 | Database driver |
| JWT | ^9.0.3 | Token authentication |
| Passport | ^0.7.0 | Authentication middleware |
| Passport-GitHub2 | ^0.1.12 | GitHub OAuth strategy |
| Bcrypt | ^6.0.0 | Password hashing |
| Multer | ^2.0.2 | File upload handling |
| Nodemailer | ^7.0.11 | Email service |
| Axios | ^1.13.2 | HTTP requests |
| WebSocket (ws) | ^8.18.3 | Real-time communication |
| Helmet | ^8.1.0 | Security headers |
| CORS | ^2.8.5 | Cross-origin support |
| Express Rate Limit | ^8.2.1 | Rate limiting |
| @Octokit/REST | ^22.0.1 | GitHub API client |

### Python Dependencies (Conversion Engine)
| Package | Version | Purpose |
|---------|---------|---------|
| Flask | 3.0.0 | Web micro-framework |
| Flask-SQLAlchemy | 3.1.1 | ORM layer |
| Flask-JWT-Extended | 4.5.3 | JWT authentication |
| SQLAlchemy | 2.0.48 | Database ORM |
| Flask-Mail | 0.9.1 | Email integration |
| psycopg | 3.1.9 | PostgreSQL adapter |
| PyYAML | 6.0.1 | Configuration parsing |
| Requests | 2.31.0 | HTTP library |
| Cryptography | 41.0.7 | Encryption support |

### Backend Structure

```
FrameShift_Server/
├── app/                   # Flask application
│   ├── __init__.py        # App initialization
│   ├── extensions.py      # SQLAlchemy & extensions
│   ├── middleware/        # Custom middleware
│   ├── models/            # Database models
│   │   ├── user.py
│   │   ├── project.py
│   │   ├── conversion_job.py
│   │   ├── report.py
│   │   ├── github_repo.py
│   │   └── verification_token.py
│   ├── routes/            # API endpoints
│   │   ├── auth.py
│   │   ├── conversion.py
│   │   ├── project.py
│   │   ├── github.py
│   │   ├── user.py
│   │   └── admin.py
│   ├── services/          # Business logic
│   │   ├── auth_service.py
│   │   ├── conversion_service.py
│   │   ├── email_service.py
│   │   ├── github_service.py
│   │   └── storage_service.py
│   ├── utils/             # Utilities
│   │   ├── decorators.py
│   │   ├── errors.py
│   │   ├── file_handler.py
│   │   ├── encryption.py
│   │   └── logger.py
│   ├── validation/        # Input validation schemas
│   │   └── schemas.py
│   └── logs/              # Application logs
├── python/                # Django conversion engine
│   ├── __init__.py
│   ├── __main__.py
│   ├── main.py
│   ├── analyzers/         # Code analysis tools
│   ├── converters/        # Conversion logic
│   ├── generators/        # Code generators
│   ├── providers/         # Data providers
│   ├── report_generators/ # Report generation
│   ├── rules/             # Conversion rules
│   ├── services/          # Services
│   ├── utils/             # Utilities
│   └── verifiers/         # Conversion verification
├── src/                   # Express.js API
│   ├── index.js           # Server entry point
│   ├── config/            # Configuration
│   ├── controllers/       # Request handlers
│   ├── middleware/        # Express middleware
│   ├── models/            # Data models
│   ├── routes/            # Route definitions
│   ├── services/          # Business services
│   ├── templates/         # Email templates
│   ├── utils/             # Utilities
│   ├── validation/        # Input validation
│   └── websocket/         # WebSocket handlers
├── database/              # Database management
│   ├── migrate.js         # Migration runner
│   └── migrations/        # SQL migration files
├── storage/               # File storage
│   ├── uploads/           # Uploaded projects
│   ├── converted/         # Converted projects
│   ├── projects/          # Project data
│   └── reports/           # Generated reports
└── config.py              # Python configuration
```

### API Routes

#### Authentication Routes (`/api/auth`)
- `POST /api/auth/register` - User registration
- `POST /api/auth/login` - Email/password login
- `POST /api/auth/oauth/github` - GitHub OAuth
- `POST /api/auth/refresh` - Refresh JWT token
- `POST /api/auth/logout` - Logout user
- `POST /api/auth/forgot-password` - Request password reset
- `POST /api/auth/reset-password` - Reset password

#### Project Routes (`/api/projects`)
- `POST /api/projects` - Create new project
- `GET /api/projects` - List user projects
- `GET /api/projects/:id` - Get project details
- `PUT /api/projects/:id` - Update project
- `DELETE /api/projects/:id` - Delete project

#### Conversion Routes (`/api/conversions`)
- `POST /api/conversions` - Create conversion job
- `GET /api/conversions/:id` - Get conversion status
- `GET /api/conversions` - List conversion jobs
- `POST /api/conversions/:id/cancel` - Cancel conversion

#### GitHub Routes (`/api/github`)
- `GET /api/github/repos` - List user GitHub repos
- `POST /api/github/import` - Import repository

#### Admin Routes (`/api/admin`)
- `GET /api/admin/users` - List all users
- `GET /api/admin/statistics` - System statistics
- `PUT /api/admin/users/:id` - Update user
- `DELETE /api/admin/users/:id` - Delete user

#### User Routes (`/api/users`)
- `GET /api/users/profile` - Get user profile
- `PUT /api/users/profile` - Update profile
- `POST /api/users/change-password` - Change password

---

## Database Overview

### Database System
- **Type**: PostgreSQL 12+
- **ORM**: SQLAlchemy (Python) / native SQL
- **Connection Pool**: 20 connections, 3600s recycle time

### Database Schema

#### Users Table
```sql
├── id (UUID PRIMARY KEY)
├── email (VARCHAR 255, UNIQUE, INDEXED)
├── full_name (VARCHAR 255)
├── password_hash (VARCHAR 255)
├── role (VARCHAR 50, DEFAULT: 'user', INDEXED)
├── github_id (VARCHAR 255, UNIQUE)
├── github_username (VARCHAR 255)
├── github_access_token (TEXT)
├── avatar_url (TEXT)
├── email_verified (BOOLEAN, DEFAULT: FALSE)
├── auth_provider (VARCHAR 50, DEFAULT: 'email')
├── last_login (DATETIME)
├── created_at (DATETIME)
└── updated_at (DATETIME)
```

#### Projects Table
```sql
├── id (UUID PRIMARY KEY)
├── user_id (UUID FOREIGN KEY → users.id)
├── name (VARCHAR 255)
├── description (TEXT)
├── source_type (VARCHAR 50) -- 'upload' or 'github'
├── source_url (TEXT)
├── file_path (TEXT)
├── size_bytes (BIGINT)
├── django_version (VARCHAR 50)
├── structure_detected (JSON)
├── created_at (DATETIME)
├── updated_at (DATETIME)
└── UNIQUE(user_id, name)
└── INDEX(user_id, source_type)
```

#### Conversion Jobs Table
```sql
├── id (UUID PRIMARY KEY)
├── project_id (UUID FOREIGN KEY → projects.id, INDEXED)
├── user_id (UUID FOREIGN KEY → users.id, INDEXED)
├── status (VARCHAR 50, INDEXED) -- pending, analyzing, converting, verifying, completed, failed
├── progress_percentage (INTEGER, DEFAULT: 0)
├── current_step (VARCHAR 255)
├── converted_file_path (TEXT)
├── error_message (TEXT)
├── started_at (DATETIME)
├── completed_at (DATETIME)
├── use_ai (BOOLEAN, DEFAULT: TRUE)
├── ai_enhancements (JSON)
├── conversion_mode (VARCHAR 50, DEFAULT: 'default') -- default or custom
├── custom_api_config (JSON)
├── retry_count (INTEGER, DEFAULT: 0)
├── last_retry_at (DATETIME)
├── created_at (DATETIME)
├── updated_at (DATETIME)
└── INDEX(user_id, status)
```

#### Reports Table
```sql
├── id (UUID PRIMARY KEY)
├── conversion_job_id (UUID FOREIGN KEY → conversion_jobs.id)
├── user_id (UUID FOREIGN KEY → users.id)
├── report_data (JSON)
├── status (VARCHAR 50) -- pending, completed, failed
├── file_path (TEXT)
├── created_at (DATETIME)
└── updated_at (DATETIME)
```

#### GitHub Repos Table
```sql
├── id (UUID PRIMARY KEY)
├── user_id (UUID FOREIGN KEY → users.id)
├── conversion_job_id (UUID FOREIGN KEY → conversion_jobs.id, nullable)
├── repo_name (VARCHAR 255)
├── repo_url (VARCHAR 255)
├── branch (VARCHAR 255, DEFAULT: 'main')
├── created_at (DATETIME)
└── updated_at (DATETIME)
```

#### Verification Tokens Table
```sql
├── id (UUID PRIMARY KEY)
├── user_id (UUID FOREIGN KEY → users.id)
├── token (VARCHAR 255, UNIQUE)
├── token_type (VARCHAR 50) -- 'email_verification', 'password_reset'
├── expires_at (DATETIME)
├── created_at (DATETIME)
└── updated_at (DATETIME)
```

### Database Migrations
| Migration | Purpose |
|-----------|---------|
| 001_create_users_table.sql | Initial users table |
| 002_create_projects_table.sql | Projects table |
| 003_create_conversion_jobs_table.sql | Conversion jobs |
| 004_create_reports_table.sql | Reports table |
| 005_create_github_repos_table.sql | GitHub repos integration |
| 006_create_verification_tokens_table.sql | Email verification |
| 007_add_auth_provider_column.sql | OAuth support |
| 008_add_retry_fields.sql | Retry logic |
| 009_add_file_diffs_column.sql | Diff tracking |
| 010_add_ai_enhancement_fields.sql | AI enhancements |
| 011_add_role_to_users.sql | User roles/permissions |
| 012_add_custom_api_mode_to_conversion_jobs.sql | Custom API mode |
| 013_add_unique_constraint_projects.sql | Unique project names |
| 014_add_validated_status_and_unique_report.sql | Report validation |
| 015_add_notification_status_to_conversion_jobs.sql | Notifications |
| 016_add_status_validation_constraint.sql | Status validation |

---

## System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Client Layer (port 3001)                │
│                                                              │
│  Next.js Frontend (React, TypeScript)                       │
│  - Authentication UI                                        │
│  - Project Management                                       │
│  - Conversion Interface                                     │
│  - Dashboard & Reports                                      │
│  - Admin Panel                                              │
│                                                              │
│  State Management: Zustand + React Query                    │
│  Real-time: WebSocket                                       │
└─────────────────────────────────────────────────────────────┘
                           ↓ HTTP/WebSocket
┌─────────────────────────────────────────────────────────────┐
│                     API Layer (port 3000)                   │
│                                                              │
│  Express.js Server (Node.js)                                │
│  - Authentication (JWT, OAuth)                              │
│  - Project Management                                       │
│  - WebSocket Connections                                    │
│  - File Upload Handling                                     │
│  - GitHub Integration                                       │
│  - Email Service                                            │
│  - Rate Limiting & Security                                │
│                                                              │
│  Services Layer:                                            │
│  - Auth Service    - GitHub Service                         │
│  - Email Service   - Storage Service                        │
└─────────────────────────────────────────────────────────────┘
                    ↓ gRPC/Inter-process
┌─────────────────────────────────────────────────────────────┐
│            Conversion Engine (Python)                       │
│                                                              │
│  Django to Next.js Converter                                │
│  - Code Analyzer (Parsers & AST)                            │
│  - Conversion Rules Engine                                  │
│  - Code Generators (Next.js compatible)                     │
│  - Report Generator                                         │
│  - Verification & Validation                                │
│                                                              │
│  AI Integration:                                            │
│  - Google Generative AI for enhancements                    │
│  - Code improvement suggestions                             │
└─────────────────────────────────────────────────────────────┘
                           ↓ SQL
┌─────────────────────────────────────────────────────────────┐
│              PostgreSQL Database                             │
│                                                              │
│  - User Management                                          │
│  - Projects & Conversion Jobs                               │
│  - Reports & Audit Logs                                     │
│  - GitHub Repos Integration                                 │
│  - Verification Tokens                                      │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow: Conversion Process

```
1. User uploads Django project or selects GitHub repo
   ↓
2. Project stored in PostgreSQL & storage/uploads/
   ↓
3. Conversion job created with status: 'pending'
   ↓
4. Backend initiates conversion process
   ├─ Status: 'analyzing' → Python analyzer parses code
   ├─ Status: 'converting' → Converters generate Next.js code
   ├─ Status: 'verifying' → Verifiers validate output
   └─ Status: 'completed' or 'failed'
   ↓
5. Real-time updates sent via WebSocket to frontend
   ↓
6. Report generated and stored
   ↓
7. Converted files available for download
```

---

## Security Features

### Authentication & Authorization
- JWT tokens (7-day expiration)
- Password hashing with bcrypt
- Email verification requirement
- GitHub OAuth 2.0 integration
- Role-based access control (admin, user)
- CORS protection

### Security Middleware
- Helmet.js for security headers
- Express Rate Limiting
- CSRF protection
- Input validation (Express Validator, Joi)
- File upload validation
- Encryption for sensitive data

### Data Protection
- Password hashing with bcrypt
- Sensitive tokens encrypted
- Secure WebSocket connections
- Secure session management with JWT
- Database connection pooling with pre-ping

---

## Deployment & Configuration

### Environment Variables
Essential configuration via `.env`:
- `JWT_SECRET` - JWT signing secret
- `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` - Database
- `FRONTEND_URL` - Frontend origin for CORS
- `EMAIL_HOST`, `EMAIL_USER`, `EMAIL_PASSWORD` - Email service
- `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET` - GitHub OAuth
- `GOOGLE_API_KEY` - Google Generative AI

### Package Scripts

**Client**:
```bash
npm run dev        # Development server (port 3001)
npm run build      # Production build
npm start          # Start production server
npm run lint       # ESLint check
```

**Server**:
```bash
npm run dev        # Development with nodemon
npm run start      # Production start
npm run migrate    # Database migrations
npm run test       # Jest tests
```

---

## Performance & Scalability

### Optimizations
- Database connection pooling (20 connections)
- JWT-based stateless authentication
- File compression for uploads
- Lazy loading in frontend
- Code splitting with Next.js
- Rate limiting on API endpoints
- WebSocket for real-time updates
- Caching strategies with React Query

### Monitoring
- Winston logger for backend logs
- Error tracking and reporting
- Request/response logging
- Database query monitoring
- Performance metrics collection

---

## Current Status
- **Frontend**: ✅ Fully functional
- **Backend**: ✅ Fully functional
- **Database**: ✅ PostgreSQL with 16 migrations
- **Last Push**: April 11, 2026
- **Repositories**: 
  - Client: https://github.com/abrarpatel0/frameshift-client2
  - Server: https://github.com/abrarpatel0/frameshift-server2

---

## Summary

FrameShift is a full-stack Django-to-Next.js migration platform with:
- **Modern Frontend**: React + Next.js with real-time updates
- **Robust Backend**: Node.js Express API + Python conversion engine
- **Secure Database**: PostgreSQL with comprehensive schema
- **Enterprise Features**: OAuth, email verification, admin panel, AI enhancements
- **Scalable Architecture**: Stateless APIs, connection pooling, rate limiting
