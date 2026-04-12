# 🚀 FrameShift Backend

### AI-Powered Django ➝ Flask Migration Engine

![Node](https://img.shields.io/badge/node-18+-green)
![Python](https://img.shields.io/badge/python-3.9+-blue)
![Status](https://img.shields.io/badge/status-production--ready-success)

---

## 📌 Overview

FrameShift is a **hybrid backend system** that automatically converts Django projects into Flask applications using a combination of:

* ⚙️ Rule-based AST transformation
* 🤖 AI-assisted verification (Google Gemini)
* 🔄 Real-time processing with WebSockets

It is designed as a **production-ready developer tool** for seamless framework migration.

---

## ✨ Key Features

* 📦 Upload Django projects (ZIP or GitHub URL)
* 🔍 Automatic project analysis & structure detection
* 🔄 Django ➝ Flask conversion
* 🤖 AI-powered verification using Gemini
* ⚡ Real-time progress tracking (WebSockets)
* 📥 Download converted project
* 🔗 Push converted code directly to GitHub
* 📧 Email notifications
* 🧹 Auto-cleanup of temporary files

---

## 🏗️ Architecture

FrameShift uses a **hybrid architecture**:

```text
Client → Express API → Python Engine → AI Verification → Output
```

### 🔹 Components

* **Node.js (Express)** → API, Auth, WebSocket, File Handling
* **Python Engine** → Code analysis & conversion
* **PostgreSQL** → Database
* **WebSocket** → Real-time updates
* **Gemini API** → AI verification

---

## 📁 Project Structure

```text
frameshift-server/
│
├── src/                # Express.js backend
│   ├── config/
│   ├── controllers/
│   ├── middleware/
│   ├── models/
│   ├── routes/
│   ├── services/
│   ├── utils/
│   └── websocket/
│
├── python/             # Conversion engine
│   ├── analyzers/
│   ├── converters/
│   ├── rules/
│   ├── verifiers/
│   ├── report_generators/
│   └── main.py
│
├── database/           # Migrations
├── tests/              # Test cases
│
├── storage/            # (ignored in git)
├── logs/               # (ignored in git)
│
├── .env.example
├── .gitignore
├── package.json
└── README.md
```

---

## ⚙️ Installation

### 1️⃣ Clone Repository

```bash
git clone https://github.com/your-username/frameshift-server.git
cd frameshift-server
```

---

### 2️⃣ Install Dependencies

#### Node.js

```bash
npm install
```

#### Python

```bash
cd python
pip install -r requirements.txt
cd ..
```

---

### 3️⃣ Setup Environment Variables

```bash
cp .env.example .env
```

Fill required values:

```env
DATABASE_URL=
JWT_SECRET=
GEMINI_API_KEY=
GITHUB_CLIENT_ID=
GITHUB_CLIENT_SECRET=
SMTP_HOST=
SMTP_PORT=
SMTP_USER=
SMTP_PASS=
```

---

### 4️⃣ Setup Database

```bash
createdb frameshift
npm run migrate
```

---

## ▶️ Running the Project

### Development

```bash
npm run dev
```

### Production

```bash
npm start
```

📍 Server runs on:

```
http://localhost:3000
```

---

## 🔌 API Endpoints

### 🔐 Authentication

* `POST /api/auth/register`
* `POST /api/auth/login`
* `POST /api/auth/logout`
* `POST /api/auth/refresh`
* `GET /api/auth/me`

### ❤️ Health Check

* `GET /health`

---

## 🔄 Conversion Pipeline

1. Upload / Clone Project
2. Analyze Django Structure
3. Convert Code

   * Models → SQLAlchemy
   * Views → Flask Routes
   * URLs → Blueprints
   * Templates → Jinja2
4. AI Verification
5. Report Generation
6. Download / GitHub Push

---

## 🔐 Security

* JWT Authentication
* Rate Limiting
* Helmet Security Headers
* Password Hashing (bcrypt)
* Input Validation
* SQL Injection Protection

---

## 🧪 Testing

```bash
npm test
```

---

## 🧹 Logs

Stored in:

```text
logs/
```

* combined.log
* error.log
* exceptions.log

---

## 🚀 Deployment

You can deploy using:

* 🌐 Render
* 🚀 Railway
* ☁️ AWS / GCP

---

## 🤝 Contributing

Contributions are welcome!

```bash
fork → create branch → commit → push → pull request
```

---

## 📄 License

ISC License

---

## 👨‍💻 Author

**Abrar Patel**
Full Stack Developer

---

## ⭐ Support

If you like this project, give it a ⭐ on GitHub!
