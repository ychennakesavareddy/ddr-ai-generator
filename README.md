<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>AI DDR Report Generator</title>
  <!-- Tailwind CSS via CDN -->
  <script src="https://cdn.tailwindcss.com"></script>
  <!-- Font Awesome for icons -->
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css" />
  <style>
    body {
      background: linear-gradient(145deg, #f6f9fc 0%, #edf2f7 100%);
      min-height: 100vh;
      font-family: 'Inter', system-ui, -apple-system, sans-serif;
    }
    .card {
      background: rgba(255,255,255,0.8);
      backdrop-filter: blur(10px);
      -webkit-backdrop-filter: blur(10px);
      border: 1px solid rgba(255,255,255,0.5);
      box-shadow: 0 8px 32px rgba(0,0,0,0.06);
    }
    .drop-zone {
      border: 2px dashed #cbd5e1;
      transition: all 0.2s ease;
      background: rgba(255,255,255,0.5);
    }
    .drop-zone.dragover {
      border-color: #3b82f6;
      background: rgba(59,130,246,0.05);
      transform: scale(1.01);
    }
    .step-indicator .step {
      transition: all 0.3s ease;
    }
    .step-indicator .step.active {
      background: #3b82f6;
      color: white;
      box-shadow: 0 4px 12px rgba(59,130,246,0.3);
    }
    .step-indicator .step.done {
      background: #10b981;
      color: white;
    }
    .report-card {
      background: white;
      border-radius: 20px;
      box-shadow: 0 12px 40px rgba(0,0,0,0.06);
      transition: all 0.2s;
    }
    .report-card:hover {
      box-shadow: 0 20px 60px rgba(0,0,0,0.08);
    }
    .severity-badge {
      font-size: 0.7rem;
      font-weight: 600;
      padding: 0.2rem 0.8rem;
      border-radius: 30px;
      letter-spacing: 0.02em;
    }
    .severity-critical { background: #fee2e2; color: #b91c1c; }
    .severity-high { background: #fef3c7; color: #92400e; }
    .severity-medium { background: #dbeafe; color: #1e40af; }
    .severity-low { background: #d1fae5; color: #065f46; }
  </style>
</head>
<body>
  <div id="root" class="max-w-7xl mx-auto px-4 py-8 md:py-12">
    <!-- Header -->
    <header class="flex flex-col md:flex-row md:items-center md:justify-between mb-8">
      <div>
        <h1 class="text-3xl md:text-4xl font-bold tracking-tight text-slate-800 flex items-center gap-3">
          <i class="fas fa-robot text-blue-600 text-3xl"></i>
          AI DDR Report Generator
        </h1>
        <p class="text-slate-500 mt-1 flex items-center gap-2">
          <i class="fas fa-file-pdf text-red-400"></i>
          Upload Inspection & Thermal PDFs → AI analysis → Professional DDR
        </p>
      </div>
      <div class="flex items-center gap-3 mt-4 md:mt-0">
        <span class="text-xs bg-blue-50 text-blue-700 px-3 py-1 rounded-full border border-blue-100">
          <i class="fas fa-bolt mr-1"></i> Gemini 2.5 Flash
        </span>
        <span class="text-xs bg-slate-100 text-slate-600 px-3 py-1 rounded-full">
          <i class="fas fa-cloud-upload-alt mr-1"></i> v2.0
        </span>
      </div>
    </header>

    <!-- Main Grid -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <!-- Left Panel: Upload & Progress -->
      <div class="lg:col-span-1 space-y-6">
        <!-- Upload Card -->
        <div class="card rounded-2xl p-6">
          <h2 class="text-lg font-semibold text-slate-700 flex items-center gap-2 mb-4">
            <i class="fas fa-upload text-blue-500"></i> Upload Reports
          </h2>
          <div id="dropZone" class="drop-zone rounded-xl p-6 text-center cursor-pointer transition">
            <i class="fas fa-cloud-upload-alt text-4xl text-slate-300 mb-3"></i>
            <p class="text-sm font-medium text-slate-600">Drop PDFs here or click to browse</p>
            <p class="text-xs text-slate-400 mt-1">Supports Inspection & Thermal reports</p>
            <input type="file" id="fileInput" accept=".pdf" multiple class="hidden" />
          </div>
          <div id="fileList" class="mt-4 space-y-2 text-sm"></div>
          <button id="generateBtn" disabled class="mt-5 w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium py-2.5 px-4 rounded-xl transition flex items-center justify-center gap-2">
            <i class="fas fa-cogs"></i> Generate DDR
          </button>
        </div>

        <!-- Progress / Steps -->
        <div class="card rounded-2xl p-6">
          <h3 class="text-sm font-semibold text-slate-700 flex items-center gap-2 mb-4">
            <i class="fas fa-spinner text-blue-500"></i> Processing Steps
          </h3>
          <div class="step-indicator space-y-3">
            <div class="step flex items-center gap-3 p-2 rounded-lg bg-slate-50/50" data-step="1">
              <span class="w-7 h-7 flex items-center justify-center rounded-full bg-slate-200 text-slate-600 text-xs font-bold">1</span>
              <span class="text-slate-600 text-sm">PDF Extraction</span>
              <i class="fas fa-check-circle text-green-500 ml-auto hidden"></i>
            </div>
            <div class="step flex items-center gap-3 p-2 rounded-lg bg-slate-50/50" data-step="2">
              <span class="w-7 h-7 flex items-center justify-center rounded-full bg-slate-200 text-slate-600 text-xs font-bold">2</span>
              <span class="text-slate-600 text-sm">AI Analysis</span>
              <i class="fas fa-check-circle text-green-500 ml-auto hidden"></i>
            </div>
            <div class="step flex items-center gap-3 p-2 rounded-lg bg-slate-50/50" data-step="3">
              <span class="w-7 h-7 flex items-center justify-center rounded-full bg-slate-200 text-slate-600 text-xs font-bold">3</span>
              <span class="text-slate-600 text-sm">DDR Generation</span>
              <i class="fas fa-check-circle text-green-500 ml-auto hidden"></i>
            </div>
          </div>
          <div id="progressStatus" class="mt-3 text-xs text-slate-400 italic">Ready</div>
        </div>

        <!-- Architecture mini -->
        <div class="card rounded-2xl p-4 text-xs text-slate-500 border border-slate-100">
          <div class="flex items-center gap-2 mb-1">
            <i class="fas fa-project-diagram text-blue-400"></i>
            <span class="font-medium text-slate-600">AI Engine: Gemini → Groq → Cohere → HuggingFace</span>
          </div>
          <div class="flex gap-1 flex-wrap">
            <span class="bg-blue-50 px-2 py-0.5 rounded text-blue-700">Gemini 2.5</span>
            <span class="bg-purple-50 px-2 py-0.5 rounded text-purple-700">Groq Llama 3.3</span>
            <span class="bg-cyan-50 px-2 py-0.5 rounded text-cyan-700">Cohere Command</span>
            <span class="bg-amber-50 px-2 py-0.5 rounded text-amber-700">HuggingFace</span>
          </div>
        </div>
      </div>

      <!-- Right Panel: Report Output -->
      <div class="lg:col-span-2 space-y-6">
        <div class="card rounded-2xl p-6 min-h-[300px] flex flex-col">
          <div class="flex items-center justify-between mb-4">
            <h2 class="text-lg font-semibold text-slate-700 flex items-center gap-2">
              <i class="fas fa-file-alt text-blue-500"></i> Generated DDR
            </h2>
            <div class="flex gap-2">
              <button id="downloadPdfBtn" disabled class="text-sm bg-emerald-50 hover:bg-emerald-100 text-emerald-700 px-3 py-1.5 rounded-lg transition flex items-center gap-1">
                <i class="fas fa-file-pdf"></i> PDF
              </button>
              <button id="downloadJsonBtn" disabled class="text-sm bg-indigo-50 hover:bg-indigo-100 text-indigo-700 px-3 py-1.5 rounded-lg transition flex items-center gap-1">
                <i class="fas fa-code"></i> JSON
              </button>
            </div>
          </div>
          <div id="reportContent" class="flex-1 overflow-y-auto max-h-[500px] text-sm text-slate-600 space-y-4">
            <div class="flex flex-col items-center justify-center h-full text-slate-400">
              <i class="fas fa-file-pdf text-5xl mb-3 opacity-20"></i>
              <p>Upload Inspection & Thermal PDFs and click "Generate DDR"</p>
              <p class="text-xs mt-1">AI will analyse, detect conflicts, and produce a professional report</p>
            </div>
          </div>
        </div>
        <!-- Mock severity legend -->
        <div class="flex flex-wrap gap-2 text-xs">
          <span class="severity-badge severity-critical"><i class="fas fa-circle mr-1"></i>Critical</span>
          <span class="severity-badge severity-high"><i class="fas fa-circle mr-1"></i>High</span>
          <span class="severity-badge severity-medium"><i class="fas fa-circle mr-1"></i>Medium</span>
          <span class="severity-badge severity-low"><i class="fas fa-circle mr-1"></i>Low</span>
        </div>
      </div>
    </div>
  </div>

  <!-- JavaScript - all in one file (simulated backend + AI flow) -->
  <script>
    (function() {
      "use strict";

      // ---------- DOM refs ----------
      const dropZone = document.getElementById('dropZone');
      const fileInput = document.getElementById('fileInput');
      const fileList = document.getElementById('fileList');
      const generateBtn = document.getElementById('generateBtn');
      const reportContent = document.getElementById('reportContent');
      const downloadPdfBtn = document.getElementById('downloadPdfBtn');
      const downloadJsonBtn = document.getElementById('downloadJsonBtn');
      const progressStatus = document.getElementById('progressStatus');
      const steps = document.querySelectorAll('.step');

      let uploadedFiles = [];

      // ---------- Helpers ----------
      function updateStep(stepNumber, state) {
        steps.forEach((el, idx) => {
          const num = idx + 1;
          const circle = el.querySelector('span:first-child');
          const check = el.querySelector('.fa-check-circle');
          if (num < stepNumber) {
            el.classList.add('done');
            el.classList.remove('active');
            circle.className = 'w-7 h-7 flex items-center justify-center rounded-full bg-green-500 text-white text-xs font-bold';
            check.classList.remove('hidden');
          } else if (num === stepNumber) {
            el.classList.add('active');
            el.classList.remove('done');
            circle.className = 'w-7 h-7 flex items-center justify-center rounded-full bg-blue-600 text-white text-xs font-bold';
            check.classList.add('hidden');
          } else {
            el.classList.remove('active', 'done');
            circle.className = 'w-7 h-7 flex items-center justify-center rounded-full bg-slate-200 text-slate-600 text-xs font-bold';
            check.classList.add('hidden');
          }
        });
      }

      function setStatus(msg, isError = false) {
        progressStatus.textContent = msg;
        progressStatus.className = 'mt-3 text-xs ' + (isError ? 'text-red-500' : 'text-slate-400');
      }

      // ---------- File handling ----------
      function handleFiles(files) {
        const pdfFiles = Array.from(files).filter(f => f.type === 'application/pdf' || f.name.endsWith('.pdf'));
        if (pdfFiles.length === 0) {
          alert('Please select PDF files only.');
          return;
        }
        uploadedFiles = pdfFiles;
        renderFileList();
        generateBtn.disabled = false;
        // reset report
        reportContent.innerHTML = `<div class="flex flex-col items-center justify-center h-full text-slate-400">
          <i class="fas fa-file-pdf text-5xl mb-3 opacity-20"></i>
          <p>${uploadedFiles.length} PDF(s) ready. Click Generate.</p>
        </div>`;
        downloadPdfBtn.disabled = true;
        downloadJsonBtn.disabled = true;
        setStatus(`${uploadedFiles.length} file(s) uploaded. Ready.`);
      }

      function renderFileList() {
        fileList.innerHTML = uploadedFiles.map(f => 
          `<div class="flex items-center justify-between bg-slate-50 p-2 rounded-lg border border-slate-100">
            <span class="truncate max-w-[150px]"><i class="fas fa-file-pdf text-red-400 mr-2"></i>${f.name}</span>
            <span class="text-xs text-slate-400">${(f.size/1024).toFixed(0)} KB</span>
          </div>`
        ).join('');
      }

      // Drop / click events
      dropZone.addEventListener('dragover', (e) => { e.preventDefault(); dropZone.classList.add('dragover'); });
      dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
      dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        if (e.dataTransfer.files.length) handleFiles(e.dataTransfer.files);
      });
      dropZone.addEventListener('click', () => fileInput.click());
      fileInput.addEventListener('change', (e) => {
        if (e.target.files.length) handleFiles(e.target.files);
        fileInput.value = '';
      });

      // ---------- Simulated AI + DDR generation (full flow) ----------
      async function generateDDR() {
        if (uploadedFiles.length === 0) return;

        // Disable button
        generateBtn.disabled = true;
        generateBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';
        setStatus('Starting PDF extraction...');
        updateStep(1, 'active');
        downloadPdfBtn.disabled = true;
        downloadJsonBtn.disabled = true;

        try {
          // Simulate step 1: PDF extraction (text + images)
          await sleep(800);
          setStatus('Extracting text & images from PDFs...');
          await sleep(700);
          // Simulate extracted data
          const extractedText = `Inspection Report: Found 3 anomalies in HVAC system. 
Thermal Report: Detected overheating in panel P-12 (65°C). 
Conflict: Inspection mentions "normal operation" but thermal shows elevated temp.`;
          const images = ['thermal_scan.png', 'inspection_photo.jpg']; // mock

          updateStep(1, 'done');
          await sleep(300);

          // Step 2: AI Analysis (Gemini → Groq → Cohere → HuggingFace fallback simulation)
          setStatus('AI Engine: Gemini 2.5 Flash analyzing...');
          updateStep(2, 'active');
          await sleep(1200);

          // Simulate AI output with conflicts, dedup, severity
          const aiResult = {
            observations: [
              { id: 1, text: 'HVAC compressor noise level high (78 dB)', severity: 'Medium', source: 'Inspection' },
              { id: 2, text: 'Panel P-12 thermal reading 65°C (above threshold 55°C)', severity: 'High', source: 'Thermal' },
              { id: 3, text: 'Air filter clogged (differential pressure 0.8 kPa)', severity: 'Low', source: 'Inspection' }
            ],
            conflicts: [
              { description: 'Inspection claims HVAC operational, thermal shows overheating', severity: 'Critical' }
            ],
            duplicates: [
              { original: 'Compressor noise', merged: 'Compressor noise & vibration' }
            ],
            rootCauses: ['Insufficient cooling airflow', 'Aged compressor bearings'],
            recommendations: ['Replace air filter', 'Schedule compressor maintenance', 'Install thermal monitoring'],
            confidence: 0.92
          };

          // Simulate fallback if needed (we just show it)
          setStatus('AI analysis complete (Gemini primary)');
          await sleep(400);
          updateStep(2, 'done');

          // Step 3: DDR Generation
          setStatus('Generating professional DDR PDF...');
          updateStep(3, 'active');
          await sleep(1000);

          // Build DDR content (mock)
          const ddrHtml = buildDDRHtml(extractedText, aiResult);
          reportContent.innerHTML = ddrHtml;
          setStatus('✅ DDR generated successfully!');
          updateStep(3, 'done');

          // Enable downloads
          downloadPdfBtn.disabled = false;
          downloadJsonBtn.disabled = false;
          generateBtn.innerHTML = '<i class="fas fa-sync-alt"></i> Regenerate';

          // Store report data for download
          window.__ddrData = { extractedText, aiResult, fullHtml: ddrHtml };

        } catch (err) {
          setStatus('Error: ' + err.message, true);
          updateStep(1, 'active');
        } finally {
          generateBtn.disabled = false;
        }
      }

      // ---------- Build DDR HTML (mocked professional report) ----------
      function buildDDRHtml(extracted, ai) {
        const obs = ai.observations.map(o => 
          `<div class="flex items-start gap-2 border-b border-slate-100 py-2">
            <span class="severity-badge severity-${o.severity.toLowerCase()}">${o.severity}</span>
            <span class="flex-1">${o.text} <span class="text-xs text-slate-400">(source: ${o.source})</span></span>
          </div>`
        ).join('');

        const conflictsHtml = ai.conflicts.map(c => 
          `<div class="flex items-start gap-2 bg-red-50 p-2 rounded-lg border border-red-100">
            <span class="severity-badge severity-${c.severity.toLowerCase()}">${c.severity}</span>
            <span>${c.description}</span>
          </div>`
        ).join('');

        const recs = ai.recommendations.map(r => `<li class="flex items-start gap-2"><i class="fas fa-check-circle text-emerald-500 mt-0.5"></i>${r}</li>`).join('');

        return `
          <div class="space-y-4">
            <div class="flex items-center justify-between border-b border-slate-200 pb-3">
              <h3 class="text-xl font-bold text-slate-800">Detailed Diagnostic Report</h3>
              <span class="text-xs bg-blue-100 text-blue-700 px-3 py-1 rounded-full">AI-Generated</span>
            </div>
            <div class="bg-slate-50 p-3 rounded-lg text-xs font-mono text-slate-500 max-h-20 overflow-y-auto">
              <i class="fas fa-quote-left mr-1"></i> ${extracted.substring(0, 150)}...
            </div>
            <div>
              <h4 class="font-semibold text-slate-700 flex items-center gap-2"><i class="fas fa-eye text-blue-500"></i> Observations</h4>
              <div class="mt-1 space-y-1">${obs}</div>
            </div>
            <div>
              <h4 class="font-semibold text-slate-700 flex items-center gap-2"><i class="fas fa-exclamation-triangle text-amber-500"></i> Conflicts & Severity</h4>
              <div class="mt-1 space-y-1">${conflictsHtml}</div>
            </div>
            <div>
              <h4 class="font-semibold text-slate-700 flex items-center gap-2"><i class="fas fa-lightbulb text-yellow-500"></i> Root Causes</h4>
              <ul class="list-disc list-inside text-slate-600 text-xs mt-1">${ai.rootCauses.map(r => `<li>${r}</li>`).join('')}</ul>
            </div>
            <div>
              <h4 class="font-semibold text-slate-700 flex items-center gap-2"><i class="fas fa-check-double text-emerald-500"></i> Recommendations</h4>
              <ul class="space-y-1 mt-1">${recs}</ul>
            </div>
            <div class="flex items-center gap-3 text-xs text-slate-400 border-t border-slate-100 pt-2">
              <span><i class="fas fa-check-circle text-green-500"></i> Confidence: ${(ai.confidence*100).toFixed(0)}%</span>
              <span><i class="fas fa-layer-group"></i> Duplicates merged: ${ai.duplicates.length}</span>
            </div>
          </div>
        `;
      }

      // ---------- Download stubs (simulated PDF/JSON) ----------
      function downloadPDF() {
        const data = window.__ddrData;
        if (!data) return;
        // In real app, this would call backend to generate PDF.
        // We simulate by downloading HTML as "PDF" (in real, would use ReportLab)
        const blob = new Blob([`<html><head><title>DDR Report</title><style>body{font-family:sans-serif;padding:2rem}</style></head><body>${data.fullHtml}</body></html>`], {type: 'application/pdf'});
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'DDR_Report_AI.pdf';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        setStatus('📥 PDF download started (simulated)');
      }

      function downloadJSON() {
        const data = window.__ddrData;
        if (!data) return;
        const json = JSON.stringify({ report: data.aiResult, extracted: data.extractedText }, null, 2);
        const blob = new Blob([json], {type: 'application/json'});
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'DDR_AI_Data.json';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        setStatus('📥 JSON download started');
      }

      // ---------- Helpers ----------
      function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

      // ---------- Event listeners ----------
      generateBtn.addEventListener('click', generateDDR);
      downloadPdfBtn.addEventListener('click', downloadPDF);
      downloadJsonBtn.addEventListener('click', downloadJSON);

      // Reset steps initially
      updateStep(1, 'inactive');
      setStatus('Upload PDFs to begin');

      // Optional: if user drops multiple, reset
      console.log('AI DDR Generator ready (Gemini → Groq → Cohere → HuggingFace)');
    })();
  </script>
</body>
</html>
