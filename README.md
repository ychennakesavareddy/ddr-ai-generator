# AI DDR Report Generator

> An intelligent, production-ready web application that automatically generates Detailed Diagnostic Reports (DDR) from Inspection and Thermal report PDFs using AI-powered analysis.

[![React](https://img.shields.io/badge/React-18.x-61DAFB?logo=react)](https://reactjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109-009688?logo=fastapi)](https://fastapi.tiangolo.com/)
[![Gemini](https://img.shields.io/badge/Gemini-API-4285F4?logo=google)](https://ai.google.dev/)
[![Tailwind](https://img.shields.io/badge/Tailwind-3.x-38B2AC?logo=tailwind-css)](https://tailwindcss.com/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## 📋 Table of Contents

- [Project Overview](#project-overview)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Installation](#installation)
- [Local Setup](#local-setup)
- [Configuration](#configuration)
- [Running the Application](#running-the-application)
- [API Endpoints](#api-endpoints)
- [Folder Structure](#folder-structure)
- [Deployment](#deployment)
- [Future Improvements](#future-improvements)
- [Contributing](#contributing)
- [License](#license)

---

## 🎯 Project Overview

The AI DDR Report Generator is a full-stack web application that automates the creation of professional Detailed Diagnostic Reports. It accepts Inspection and Thermal report PDFs, extracts text and images, analyzes the data using Google's Gemini AI, and generates a comprehensive, client-ready DDR with structured observations, severity assessments, and actionable recommendations.

### Key Benefits
- **Automated Analysis**: Eliminates manual report compilation
- **AI-Powered Insights**: Uses Gemini to detect conflicts, merge duplicates, and assess severity
- **Professional Output**: Generates polished PDF reports with corporate styling
- **Time-Saving**: Reduces report generation time from hours to minutes
- **Consistent Quality**: Ensures standardized reporting across all documents

---

## ✨ Features

### Core Functionality
- ✅ **PDF Upload**: Drag-and-drop support for Inspection and Thermal reports
- ✅ **Text Extraction**: Extracts clean text from PDFs using PyMuPDF
- ✅ **Image Extraction**: Captures and preserves images with page association
- ✅ **AI Analysis**: Gemini-powered analysis with conflict and duplicate detection
- ✅ **Structured DDR**: Generates comprehensive reports with 7 key sections
- ✅ **PDF Export**: Professional ReportLab-generated PDFs with corporate styling
- ✅ **JSON Export**: Raw data export for integration with other systems

### AI Capabilities
- **Observation Extraction**: Identifies key findings from both reports
- **Duplicate Detection**: Merges similar observations across documents
- **Conflict Detection**: Flags contradictory information between reports
- **Severity Assessment**: Assigns Low/Medium/High/Critical ratings with reasoning
- **Root Cause Analysis**: Suggests probable causes based on evidence
- **Recommendation Engine**: Generates actionable recommendations
- **Confidence Scoring**: Provides confidence metrics for AI analysis

### User Experience
- Modern, responsive corporate UI
- Real-time loading progress with step tracking
- Drag-and-drop file upload
- Report preview before download
- Error handling with user-friendly messages

---

## 🛠️ Tech Stack

### Frontend
| Technology | Version | Purpose |
|------------|---------|---------|
| React | 18.x | UI Framework |
| Tailwind CSS | 3.x | Styling |
| Axios | 1.x | HTTP Client |
| React Hooks | - | State Management |

### Backend
| Technology | Version | Purpose |
|------------|---------|---------|
| FastAPI | 0.109+ | REST API Framework |
| Python | 3.9+ | Programming Language |
| PyMuPDF (fitz) | 1.23+ | PDF Processing |
| ReportLab | 4.x | PDF Generation |
| Pillow | 10.x | Image Processing |

### AI/ML
| Technology | Purpose |
|------------|---------|
| Google Gemini API | AI Analysis & Report Generation |

### Deployment
| Platform | Purpose |
|----------|---------|
| AWS Amplify | Frontend Hosting |
| AWS EC2 | Backend Hosting |

---

## 📦 Installation

### Prerequisites
- Node.js (v18 or higher)
- Python (v3.9 or higher)
- Google Gemini API Key
- Git

### Clone Repository
```bash
git clone https://github.com/yourusername/ddr-ai-generator.git
cd ddr-ai-generator