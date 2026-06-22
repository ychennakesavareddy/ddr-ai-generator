<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AI DDR Report Generator · README</title>
  <!-- Font Awesome for icons (optional but nice) -->
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css">
  <style>
    * {
      margin: 0;
      padding: 0;
      box-sizing: border-box;
    }

    body {
      background: #f6f9fc;
      font-family: 'Segoe UI', Roboto, system-ui, -apple-system, sans-serif;
      padding: 2rem 1.5rem;
      display: flex;
      justify-content: center;
    }

    .readme-container {
      max-width: 1100px;
      width: 100%;
      background: white;
      border-radius: 32px;
      padding: 2.5rem 2.8rem;
      box-shadow: 0 20px 60px rgba(0, 20, 40, 0.08);
      transition: all 0.2s;
    }

    /* hr replacement */
    .section-divider {
      border: none;
      height: 1px;
      background: linear-gradient(90deg, #e0e8f0, #b0c8dd, #e0e8f0);
      margin: 2.5rem 0;
    }

    /* author table (replicates the markdown table) */
    .author-card {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: center;
      background: #fafcff;
      border-radius: 28px;
      padding: 1.8rem 2rem;
      margin: 1.8rem 0 0.5rem;
      border: 1px solid #eef3f9;
      gap: 1.5rem 2.5rem;
    }

    .author-avatar {
      flex-shrink: 0;
      width: 140px;
      height: 140px;
      background: #e4ecf5;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      overflow: hidden;
      border: 2px solid white;
      box-shadow: 0 8px 20px rgba(0,0,0,0.02);
    }

    .author-avatar img {
      width: 100%;
      height: 100%;
      object-fit: contain;
    }

    .author-info {
      flex: 1;
      min-width: 220px;
    }

    .author-info h3 {
      font-size: 1.8rem;
      font-weight: 600;
      letter-spacing: -0.02em;
      color: #0b1a2b;
      margin-bottom: 0.2rem;
    }

    .author-info .badge {
      display: inline-block;
      background: #eaf2fa;
      padding: 0.2rem 1rem;
      border-radius: 20px;
      font-size: 0.9rem;
      font-weight: 500;
      color: #1e4b6a;
      margin-bottom: 0.8rem;
    }

    .author-links {
      display: flex;
      flex-wrap: wrap;
      gap: 1.2rem 2rem;
      margin-top: 0.7rem;
    }

    .author-links a {
      text-decoration: none;
      color: #1a5a7a;
      font-weight: 500;
      font-size: 0.95rem;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      transition: color 0.1s;
      border-bottom: 1px dotted transparent;
    }

    .author-links a i {
      font-size: 1rem;
      width: 1.2rem;
      color: #2e6d92;
    }

    .author-links a:hover {
      color: #003153;
      border-bottom-color: #82b1d4;
    }

    /* headings */
    h1 {
      font-size: 2.8rem;
      font-weight: 700;
      letter-spacing: -0.02em;
      color: #0b263b;
      margin: 1.2rem 0 0.4rem;
    }

    h1 + p {
      font-size: 1.2rem;
      color: #2f4b62;
      margin-bottom: 1.8rem;
    }

    h2 {
      font-size: 1.9rem;
      font-weight: 600;
      margin: 2.2rem 0 1rem;
      color: #10344e;
      letter-spacing: -0.01em;
      border-bottom: 2px solid #e2edf6;
      padding-bottom: 0.3rem;
    }

    h3 {
      font-size: 1.4rem;
      font-weight: 600;
      margin: 1.8rem 0 0.8rem;
      color: #1e405b;
    }

    /* badges */
    .badge-strip {
      display: flex;
      flex-wrap: wrap;
      gap: 0.6rem 1rem;
      margin: 0.8rem 0 1.4rem;
    }

    .badge-strip span {
      background: #e9f0f8;
      padding: 0.25rem 1.1rem;
      border-radius: 30px;
      font-size: 0.85rem;
      font-weight: 500;
      color: #1d4a68;
      display: inline-flex;
      align-items: center;
      gap: 5px;
    }

    .badge-strip span i {
      font-size: 0.8rem;
      opacity: 0.7;
    }

    /* tables */
    .tech-table {
      width: 100%;
      border-collapse: collapse;
      font-size: 0.95rem;
      margin: 1.2rem 0 1.8rem;
      border-radius: 16px;
      overflow: hidden;
      box-shadow: 0 1px 4px rgba(0,0,0,0.02);
    }

    .tech-table th {
      background: #e5eef7;
      color: #13324a;
      font-weight: 600;
      padding: 0.7rem 1rem;
      text-align: left;
      border: 1px solid #d5e2ed;
    }

    .tech-table td {
      background: #fbfdff;
      padding: 0.7rem 1rem;
      border: 1px solid #dce7f1;
    }

    .tech-table tr:last-child td {
      border-bottom: 1px solid #dce7f1;
    }

    /* code / pre */
    pre {
      background: #0f1e2b;
      color: #e0edf7;
      padding: 1.4rem 1.8rem;
      border-radius: 18px;
      overflow-x: auto;
      font-size: 0.9rem;
      line-height: 1.5;
      margin: 1.2rem 0;
      border: 1px solid #1d3345;
    }

    code {
      background: #eef4fa;
      padding: 0.2rem 0.6rem;
      border-radius: 8px;
      font-size: 0.9rem;
      color: #124066;
    }

    pre code {
      background: transparent;
      color: inherit;
      padding: 0;
    }

    .inline-code {
      background: #eaf1f9;
      padding: 0.2rem 0.6rem;
      border-radius: 6px;
      font-family: 'Fira Code', monospace;
    }

    .env-box {
      background: #0b1b2a;
      color: #bcd9f0;
      padding: 1.2rem 1.8rem;
      border-radius: 18px;
      font-family: 'Fira Code', monospace;
      font-size: 0.9rem;
      line-height: 1.8;
    }

    .fallback-chain {
      background: #f2f8ff;
      padding: 1.2rem 2rem;
      border-radius: 28px;
      display: inline-block;
      border: 1px solid #d1e2f0;
      font-weight: 500;
      color: #1a405a;
      margin: 0.5rem 0 1rem;
    }

    .fallback-chain span {
      margin: 0 8px;
    }

    .future-list {
      list-style: none;
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 0.5rem 1.5rem;
      margin: 0.8rem 0 1rem;
    }

    .future-list li::before {
      content: "▹ ";
      color: #2874a6;
      font-weight: 600;
    }

    @media (max-width: 700px) {
      .readme-container {
        padding: 1.5rem 1rem;
      }
      .author-card {
        flex-direction: column;
        text-align: center;
      }
      .author-avatar {
        width: 120px;
        height: 120px;
      }
      .author-links {
        justify-content: center;
      }
      .future-list {
        grid-template-columns: 1fr;
      }
      h1 {
        font-size: 2.2rem;
      }
    }
  </style>
</head>
<body>
  <div class="readme-container">

    <!-- ========== AUTHOR CARD ========== -->
    <div class="author-card">
      <div class="author-avatar">
        <img src="https://chennareddy.in/logo.png" alt="Chenna Kesava Reddy" onerror="this.src='data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 width=%22180%22 height=%22180%22 viewBox=%220 0 180 180%22%3E%3Crect width=%22180%22 height=%22180%22 fill=%22%23d9e6f2%22/%3E%3Ctext x=%2230%22 y=%22110%22 font-family=%22Segoe UI%22 font-size=%2222%22 fill=%22%231d4d6e%22%3ECK%3C/text%3E%3C/svg%3E'">
      </div>
      <div class="author-info">
        <h3>Chenna Kesava Reddy</h3>
        <div class="badge">Final Year Computer Science Engineering Student</div>
        <div style="display: flex; flex-wrap: wrap; gap: 0.8rem 2rem; margin-bottom: 0.6rem;">
          <span><i class="fas fa-robot" style="color: #1d6f9c;"></i> AI &amp; Machine Learning</span>
          <span><i class="fas fa-code" style="color: #1d6f9c;"></i> Full Stack Development</span>
          <span><i class="fas fa-cloud" style="color: #1d6f9c;"></i> AWS EC2 &amp; Cloud Deployment</span>
          <span><i class="fas fa-brain" style="color: #1d6f9c;"></i> LLM Applications &amp; AI Automation</span>
          <span><i class="fas fa-file-pdf" style="color: #1d6f9c;"></i> Document Intelligence Systems</span>
        </div>
        <div class="author-links">
          <a href="https://github.com/ychennakesavareddy"><i class="fab fa-github"></i> github.com/ychennakesavareddy</a>
          <a href="https://www.linkedin.com/in/ychennakesavareddy"><i class="fab fa-linkedin"></i> linkedin.com/in/ychennakesavareddy</a>
          <a href="https://chennareddy.in"><i class="fas fa-globe"></i> chennareddy.in</a>
        </div>
      </div>
    </div>

    <hr class="section-divider">

    <!-- ========== TITLE ========== -->
    <h1>🚀 AI DDR Report Generator</h1>
    <p>An intelligent, production-ready web application that automatically generates Detailed Diagnostic Reports (DDR) from Inspection and Thermal Report PDFs using AI-powered analysis and multi-model reasoning.</p>

    <div class="badge-strip">
      <span><i class="fab fa-python"></i> Python 3.9+</span>
      <span><i class="fas fa-bolt"></i> FastAPI 0.109+</span>
      <span><i class="fas fa-gem"></i> Gemini 2.5 Flash</span>
      <span><i class="fas fa-cloud"></i> AWS EC2 | Amplify</span>
      <span><i class="fas fa-balance-scale"></i> MIT License</span>
    </div>

    <hr class="section-divider">

    <!-- ========== TABLE OF CONTENTS ========== -->
    <h2>📋 Table of Contents</h2>
    <ul style="columns: 2 180px; list-style: none; padding-left: 0; margin: 0.5rem 0 1rem;">
      <li style="margin-bottom: 6px;">• Project Overview</li>
      <li style="margin-bottom: 6px;">• Features</li>
      <li style="margin-bottom: 6px;">• Architecture</li>
      <li style="margin-bottom: 6px;">• Tech Stack</li>
      <li style="margin-bottom: 6px;">• Installation</li>
      <li style="margin-bottom: 6px;">• Environment Variables</li>
      <li style="margin-bottom: 6px;">• Running the Application</li>
      <li style="margin-bottom: 6px;">• API Endpoints</li>
      <li style="margin-bottom: 6px;">• Folder Structure</li>
      <li style="margin-bottom: 6px;">• Deployment</li>
      <li style="margin-bottom: 6px;">• AI Model Fallback Chain</li>
      <li style="margin-bottom: 6px;">• Future Improvements</li>
      <li style="margin-bottom: 6px;">• Author</li>
    </ul>

    <hr class="section-divider">

    <!-- ========== PROJECT OVERVIEW ========== -->
    <h2>🎯 Project Overview</h2>
    <p>The AI DDR Report Generator is an AI-powered document intelligence platform that automates the generation of Detailed Diagnostic Reports (DDR) from Inspection Reports and Thermal Imaging Reports.</p>
    <p>The system extracts text and images from uploaded PDFs, performs AI-driven analysis, identifies observations, detects conflicts, assesses severity, and generates professional PDF reports.</p>
    <div style="background: #f0f6fd; padding: 1rem 1.8rem; border-radius: 24px; margin: 1rem 0; display: flex; flex-wrap: wrap; gap: 1.5rem 3rem;">
      <div><strong>✅ Automated</strong> report generation</div>
      <div><strong>🧠 AI-powered</strong> observation analysis</div>
      <div><strong>⚡ Conflict &amp;</strong> duplicate detection</div>
      <div><strong>📄 Professional</strong> PDF export</div>
      <div><strong>🔄 Multi-model</strong> AI fallback</div>
      <div><strong>☁️ Production-ready</strong> AWS deployment</div>
    </div>

    <hr class="section-divider">

    <!-- ========== FEATURES ========== -->
    <h2>✨ Features</h2>
    <h3>📄 Document Processing</h3>
    <ul>
      <li>Upload Inspection Reports</li>
      <li>Upload Thermal Reports</li>
      <li>PDF Text Extraction</li>
      <li>Embedded Image Extraction</li>
      <li>File Validation</li>
    </ul>
    <h3>🧠 AI Analysis</h3>
    <ul>
      <li>Observation Extraction</li>
      <li>Conflict Detection</li>
      <li>Duplicate Detection</li>
      <li>Severity Assessment</li>
      <li>Root Cause Analysis</li>
      <li>Recommendation Generation</li>
      <li>Confidence Scoring</li>
    </ul>
    <h3>📑 Report Generation</h3>
    <ul>
      <li>Executive Summary</li>
      <li>Findings &amp; Observations</li>
      <li>Severity Analysis</li>
      <li>Root Cause Analysis</li>
      <li>Recommendations</li>
      <li>Confidence Metrics</li>
      <li>Professional PDF Export</li>
    </ul>
    <h3>👤 User Experience</h3>
    <ul>
      <li>Drag &amp; Drop Upload</li>
      <li>Real-Time Progress Tracking</li>
      <li>Responsive UI</li>
      <li>Error Handling</li>
      <li>Downloadable Reports</li>
    </ul>

    <hr class="section-divider">

    <!-- ========== ARCHITECTURE ========== -->
    <h2>🏗️ Architecture</h2>
    <pre>
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
    </pre>

    <hr class="section-divider">

    <!-- ========== TECH STACK ========== -->
    <h2>🛠️ Tech Stack</h2>
    <h3>Frontend</h3>
    <table class="tech-table">
      <tr><th>Technology</th><th>Purpose</th></tr>
      <tr><td>HTML5</td><td>User Interface</td></tr>
      <tr><td>CSS3</td><td>Styling</td></tr>
      <tr><td>JavaScript</td><td>Client Logic</td></tr>
      <tr><td>AWS Amplify</td><td>Hosting</td></tr>
    </table>
    <h3>Backend</h3>
    <table class="tech-table">
      <tr><th>Technology</th><th>Purpose</th></tr>
      <tr><td>Python</td><td>Backend Development</td></tr>
      <tr><td>FastAPI</td><td>REST APIs</td></tr>
      <tr><td>Uvicorn</td><td>ASGI Server</td></tr>
      <tr><td>Nginx</td><td>Reverse Proxy</td></tr>
    </table>
    <h3>PDF Processing</h3>
    <table class="tech-table">
      <tr><th>Technology</th><th>Purpose</th></tr>
      <tr><td>PyMuPDF</td><td>Text Extraction</td></tr>
      <tr><td>Pillow</td><td>Image Processing</td></tr>
      <tr><td>ReportLab</td><td>PDF Generation</td></tr>
    </table>
    <h3>AI Models</h3>
    <table class="tech-table">
      <tr><th>Model</th><th>Role</th></tr>
      <tr><td>Gemini 2.5 Flash</td><td>Primary Model</td></tr>
      <tr><td>Groq Llama 3.3 70B</td><td>Fallback 1</td></tr>
      <tr><td>Cohere Command-A</td><td>Fallback 2</td></tr>
      <tr><td>Hugging Face Qwen 2.5 VL</td><td>Fallback 3</td></tr>
    </table>
    <h3>Cloud Infrastructure</h3>
    <table class="tech-table">
      <tr><th>Service</th><th>Purpose</th></tr>
      <tr><td>AWS EC2</td><td>Backend Hosting</td></tr>
      <tr><td>AWS Amplify</td><td>Frontend Hosting</td></tr>
      <tr><td>Nginx</td><td>API Routing</td></tr>
      <tr><td>GitHub</td><td>Version Control</td></tr>
    </table>

    <hr class="section-divider">

    <!-- ========== INSTALLATION ========== -->
    <h2>📦 Installation</h2>
    <h3>Clone Repository</h3>
    <pre><code>git clone https://github.com/ychennakesavareddy/ddr-ai-generator.git
cd ddr-ai-generator</code></pre>
    <h3>Create Virtual Environment</h3>
    <pre><code>python -m venv venv</code></pre>
    <h3>Activate Environment</h3>
    <p><strong>Windows</strong></p>
    <pre><code>venv\Scripts\activate</code></pre>
    <p><strong>Linux</strong></p>
    <pre><code>source venv/bin/activate</code></pre>
    <h3>Install Dependencies</h3>
    <pre><code>pip install -r requirements.txt</code></pre>

    <hr class="section-divider">

    <!-- ========== ENV ========== -->
    <h2>⚙️ Environment Variables</h2>
    <p>Create a <code>.env</code> file:</p>
    <div class="env-box">
      GEMINI_API_KEY=YOUR_KEY<br>
      GROQ_API_KEY=YOUR_KEY<br>
      COHERE_API_KEY=YOUR_KEY<br>
      HF_TOKEN=YOUR_TOKEN<br>
      AI_PROVIDER=gemini<br>
      DEFAULT_MODEL=models/gemini-2.5-flash
    </div>

    <hr class="section-divider">

    <!-- ========== RUNNING ========== -->
    <h2>🚀 Running the Application</h2>
    <h3>Backend</h3>
    <pre><code>uvicorn main:app --reload</code></pre>
    <p>Backend URL: <span class="inline-code">http://localhost:8000</span></p>
    <h3>Frontend</h3>
    <p>Open: <span class="inline-code">index.html</span> or run using Live Server.</p>

    <hr class="section-divider">

    <!-- ========== API ENDPOINTS ========== -->
    <h2>🔌 API Endpoints</h2>
    <h3>Health Check</h3>
    <pre><code>GET /</code></pre>
    <h3>Generate DDR Report</h3>
    <pre><code>POST /generate-ddr</code></pre>
    <p>Uploads inspection and thermal reports and generates a complete DDR report.</p>
    <h3>Download Report</h3>
    <pre><code>GET /download-report/{report_id}</code></pre>
    <p>Downloads generated PDF reports.</p>

    <hr class="section-divider">

    <!-- ========== FOLDER STRUCTURE ========== -->
    <h2>📁 Folder Structure</h2>
    <pre>
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
├── frontend/
│   ├── index.html
│   ├── scripts/
│   ├── styles/
│   └── assets/
└── README.md
    </pre>

    <hr class="section-divider">

    <!-- ========== FALLBACK ========== -->
    <h2>🔄 AI Model Fallback Chain</h2>
    <div class="fallback-chain">
      Gemini 2.5 Flash <span>⬇️</span> Groq Llama 3.3 70B <span>⬇️</span> Cohere Command-A <span>⬇️</span> Hugging Face Qwen 2.5 VL
    </div>
    <p>If the primary model fails due to quota, timeout, or API errors, the system automatically switches to the next available provider.</p>

    <hr class="section-divider">

    <!-- ========== DEPLOYMENT ========== -->
    <h2>🌍 Deployment</h2>
    <ul>
      <li><strong>Frontend:</strong> AWS Amplify</li>
      <li><strong>Backend:</strong> AWS EC2</li>
      <li><strong>Reverse Proxy:</strong> Nginx</li>
      <li><strong>Domain:</strong> api.chennareddy.in</li>
    </ul>

    <hr class="section-divider">

    <!-- ========== FUTURE ========== -->
    <h2>🚀 Future Improvements</h2>
    <ul class="future-list">
      <li>S3 Storage Integration</li>
      <li>CloudWatch Monitoring</li>
      <li>User Authentication</li>
      <li>Dashboard Analytics</li>
      <li>OCR for Scanned PDFs</li>
      <li>Report History</li>
      <li>RAG-Based Knowledge Base</li>
      <li>AI Agent Review System</li>
    </ul>

    <hr class="section-divider">

    <!-- ========== AUTHOR ========== -->
    <h2>👨‍💻 Author</h2>
    <p><strong>Chenna Kesava Reddy</strong></p>
    <p>GitHub: <a href="https://github.com/ychennakesavareddy">github.com/ychennakesavareddy</a><br>
    LinkedIn: <a href="https://www.linkedin.com/in/ychennakesavareddy">linkedin.com/in/ychennakesavareddy</a><br>
    Portfolio: <a href="https://chennareddy.in">chennareddy.in</a></p>

    <hr class="section-divider">

    <!-- ========== LICENSE ========== -->
    <h2>📄 License</h2>
    <p>This project is licensed under the MIT License.</p>

    <hr class="section-divider">
    <p style="text-align: center; color: #4f6d86; font-size: 0.9rem; margin-top: 1rem;">✨ AI DDR Report Generator · built with ❤️</p>
  </div>
</body>
</html>
