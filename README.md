# AI DDR Report Generator

> An intelligent, production-ready web application that automatically generates Detailed Diagnostic Reports (DDR) from Inspection and Thermal Report PDFs using AI-powered analysis and multi-model reasoning.

![Python](https://img.shields.io/badge/Python-3.9+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-green)
![Gemini](https://img.shields.io/badge/Gemini-2.5%20Flash-orange)
![AWS](https://img.shields.io/badge/AWS-EC2%20%7C%20Amplify-yellow)
![License](https://img.shields.io/badge/License-MIT-green)

---

# 📋 Table of Contents

* Project Overview
* Features
* Architecture
* Tech Stack
* Installation
* Environment Variables
* Running the Application
* API Endpoints
* Folder Structure
* Deployment
* AI Model Fallback Chain
* Future Improvements
* Author

---

# 🎯 Project Overview

The AI DDR Report Generator is an AI-powered document intelligence platform that automates the generation of Detailed Diagnostic Reports (DDR) from Inspection Reports and Thermal Imaging Reports.

The system extracts text and images from uploaded PDFs, performs AI-driven analysis, identifies observations, detects conflicts, assesses severity, and generates professional PDF reports.

### Key Benefits

* Automated report generation
* AI-powered observation analysis
* Conflict and duplicate detection
* Professional PDF export
* Multi-model AI fallback architecture
* Production-ready AWS deployment

---

# ✨ Features

## Document Processing

* Upload Inspection Reports
* Upload Thermal Reports
* PDF Text Extraction
* Embedded Image Extraction
* File Validation

## AI Analysis

* Observation Extraction
* Conflict Detection
* Duplicate Detection
* Severity Assessment
* Root Cause Analysis
* Recommendation Generation
* Confidence Scoring

## Report Generation

* Executive Summary
* Findings & Observations
* Severity Analysis
* Root Cause Analysis
* Recommendations
* Confidence Metrics
* Professional PDF Export

## User Experience

* Drag & Drop Upload
* Real-Time Progress Tracking
* Responsive UI
* Error Handling
* Downloadable Reports

---

# 🏗️ Architecture

User

↓

Frontend (AWS Amplify)

↓

Nginx Reverse Proxy

↓

FastAPI Backend (AWS EC2)

↓

PDF Processing Layer

↓

AI Processing Engine

↓

DDR Report Generator

↓

Professional PDF Report

---

# 🛠️ Tech Stack

## Frontend

| Technology  | Purpose        |
| ----------- | -------------- |
| HTML5       | User Interface |
| CSS3        | Styling        |
| JavaScript  | Client Logic   |
| AWS Amplify | Hosting        |

## Backend

| Technology | Purpose             |
| ---------- | ------------------- |
| Python     | Backend Development |
| FastAPI    | REST APIs           |
| Uvicorn    | ASGI Server         |
| Nginx      | Reverse Proxy       |

## PDF Processing

| Technology | Purpose          |
| ---------- | ---------------- |
| PyMuPDF    | Text Extraction  |
| Pillow     | Image Processing |
| ReportLab  | PDF Generation   |

## AI Models

| Model                    | Role          |
| ------------------------ | ------------- |
| Gemini 2.5 Flash         | Primary Model |
| Groq Llama 3.3 70B       | Fallback 1    |
| Cohere Command-A         | Fallback 2    |
| Hugging Face Qwen 2.5 VL | Fallback 3    |

## Cloud Infrastructure

| Service     | Purpose          |
| ----------- | ---------------- |
| AWS EC2     | Backend Hosting  |
| AWS Amplify | Frontend Hosting |
| Nginx       | API Routing      |
| GitHub      | Version Control  |

---

# 📦 Installation

## Clone Repository

```bash
git clone https://github.com/ychennakesavareddy/ddr-ai-generator.git

cd ddr-ai-generator
```

## Create Virtual Environment

```bash
python -m venv venv
```

## Activate Environment

Windows

```bash
venv\Scripts\activate
```

Linux

```bash
source venv/bin/activate
```

## Install Dependencies

```bash
pip install -r requirements.txt
```

---

# ⚙️ Environment Variables

Create a `.env` file:

```env
GEMINI_API_KEY=YOUR_KEY

GROQ_API_KEY=YOUR_KEY

COHERE_API_KEY=YOUR_KEY

HF_TOKEN=YOUR_TOKEN

AI_PROVIDER=gemini

DEFAULT_MODEL=models/gemini-2.5-flash
```

---

# 🚀 Running the Application

## Backend

```bash
uvicorn main:app --reload
```

Backend URL

```text
http://localhost:8000
```

## Frontend

Open:

```text
index.html
```

or run using Live Server.

---

# 🔌 API Endpoints

## Health Check

```http
GET /
```

## Generate DDR Report

```http
POST /generate-ddr
```

Uploads inspection and thermal reports and generates a complete DDR report.

## Download Report

```http
GET /download-report/{report_id}
```

Downloads generated PDF reports.

---

# 📁 Folder Structure

```text
ddr-ai-generator/

├── backend/
│   ├── main.py
│   ├── ai_processor.py
│   ├── ddr_generator.py
│   ├── image_extractor.py
│   ├── pdf_extractor.py
│   ├── pdf_report_generator.py
│   ├── utils.py
│   ├── uploads/
│   ├── generated_reports/
│   └── requirements.txt
│
├── frontend/
│   ├── index.html
│   ├── scripts/
│   ├── styles/
│   └── assets/
│
└── README.md
```

---

# 🔄 AI Model Fallback Chain

```text
Gemini 2.5 Flash
        ↓
Groq Llama 3.3 70B
        ↓
Cohere Command-A
        ↓
Hugging Face Qwen 2.5 VL
```

If the primary model fails due to quota, timeout, or API errors, the system automatically switches to the next available provider.

---

# 🌍 Deployment

## Frontend

AWS Amplify

## Backend

AWS EC2

## Reverse Proxy

Nginx

## Domain

api.chennareddy.in

---

# 🚀 Future Improvements

* S3 Storage Integration
* CloudWatch Monitoring
* User Authentication
* Dashboard Analytics
* OCR for Scanned PDFs
* Report History
* RAG-Based Knowledge Base
* AI Agent Review System

---

# 👨‍💻 Author

Chenna Kesava Reddy

GitHub:
https://github.com/ychennakesavareddy

LinkedIn:
https://www.linkedin.com/in/ychennakesavareddy

Portfolio:
https://chennareddy.in

---

# 📄 License

This project is licensed under the MIT License.
