/**
 * DDR AI — Enterprise Frontend Application
 * Modular architecture with SOLID principles, event delegation,
 * and production-grade state management.
 *
 * @module Homepage
 * @version 2.1.0
 */

'use strict';

/* ============================================================
   ENVIRONMENT DETECTION
   ============================================================ */

const ENV = Object.freeze({
  isDevelopment: window.location.hostname === 'localhost' || 
                 window.location.hostname === '127.0.0.1' ||
                 window.location.hostname.startsWith('192.168'),
  isProduction: window.location.hostname === 'main.dhotu9foixoyc.amplifyapp.com' ||
                window.location.hostname === 'api.chennareddy.in',
});

/* ============================================================
   CONFIGURATION
   ============================================================ */

const CONFIG = Object.freeze({
  // Dynamically determine API URL based on environment
  API_BASE_URL: ENV.isDevelopment 
    ? 'http://127.0.0.1:8000'
    : 'https://api.chennareddy.in',
  
  get API_ENDPOINT() {
    return `${this.API_BASE_URL}/generate-ddr`;
  },
  
  MAX_FILE_SIZE_MB: 20,
  ACCEPTED_TYPE: 'application/pdf',
  STEPS: [
    { id: 'extract-text',  label: 'Extracting PDF text content', description: 'Parsing PDF structure and text layers' },
    { id: 'extract-images', label: 'Extracting embedded images', description: 'Detecting and saving visual evidence' },
    { id: 'ai-analysis',    label: 'AI reasoning analysis', description: 'Gemini processing with multi-stage reasoning' },
    { id: 'conflict-detection', label: 'Conflict detection', description: 'Comparing findings across reports' },
    { id: 'merge-findings', label: 'Merging and deduplicating', description: 'Consolidating observations intelligently' },
    { id: 'generate-report', label: 'Generating DDR structure', description: 'Building comprehensive diagnostic report' },
    { id: 'build-pdf',      label: 'Building professional PDF', description: 'Formatting with enterprise design system' },
  ],
});

// Log environment and API endpoint in dev mode
if (ENV.isDevelopment) {
  console.log(
    '%c[DDR AI] Running in development mode',
    'color: #4CAF50; font-weight: bold;'
  );
  console.log(`%cAPI Endpoint: ${CONFIG.API_ENDPOINT}`, 'color: #2196F3;');
}

/* ============================================================
   DOM REFERENCES
   ============================================================ */

const DOM = Object.freeze({
  // Navigation
  statusDot: document.getElementById('statusDot'),
  statusText: document.getElementById('statusText'),
  statusMetrics: document.getElementById('statusMetrics'),

  // Hero
  processedCount: document.getElementById('processedCount'),
  avgTime: document.getElementById('avgTime'),
  accuracyRate: document.getElementById('accuracyRate'),

  // Upload: Inspection
  inspectionZone: document.getElementById('inspectionZone'),
  inspectionFile: document.getElementById('inspectionFile'),
  inspectionInfo: document.getElementById('inspectionInfo'),
  inspectionName: document.getElementById('inspectionName'),
  inspectionSize: document.getElementById('inspectionSize'),
  inspectionStatus: document.getElementById('inspectionStatus'),
  inspectionRemove: document.getElementById('inspectionRemove'),

  // Upload: Thermal
  thermalZone: document.getElementById('thermalZone'),
  thermalFile: document.getElementById('thermalFile'),
  thermalInfo: document.getElementById('thermalInfo'),
  thermalName: document.getElementById('thermalName'),
  thermalSize: document.getElementById('thermalSize'),
  thermalStatus: document.getElementById('thermalStatus'),
  thermalRemove: document.getElementById('thermalRemove'),

  // Generate
  generateBtn: document.getElementById('generateBtn'),

  // Processing
  processingPanel: document.getElementById('processingPanel'),
  processingTitle: document.getElementById('processingTitle'),
  processingSubtitle: document.getElementById('processingSubtitle'),
  processingTime: document.getElementById('processingTime'),
  processingProgress: document.getElementById('processingProgress'),
  progressBar: document.getElementById('progressBar'),
  processingSteps: document.getElementById('processingSteps'),

  // Error
  errorPanel: document.getElementById('errorPanel'),
  errorMessage: document.getElementById('errorMessage'),
  errorDetails: document.getElementById('errorDetails'),
  retryBtn: document.getElementById('retryBtn'),

  // Results Dashboard
  resultsPanel: document.getElementById('resultsPanel'),
  dashboardBadge: document.getElementById('dashboardBadge'),
  dashboardReportId: document.getElementById('dashboardReportId'),
  dashboardTimestamp: document.getElementById('dashboardTimestamp'),

  // Summary
  smAreas: document.getElementById('smAreas'),
  smSeverity: document.getElementById('smSeverity'),
  smActions: document.getElementById('smActions'),
  smConfidence: document.getElementById('smConfidence'),
  confidenceFill: document.getElementById('confidenceFill'),

  // Analytics
  analyticsCritical: document.getElementById('analyticsCritical'),
  analyticsHigh: document.getElementById('analyticsHigh'),
  analyticsMedium: document.getElementById('analyticsMedium'),
  analyticsLow: document.getElementById('analyticsLow'),

  // Results sections
  rsSummary: document.getElementById('rsSummary'),
  obsCount: document.getElementById('obsCount'),
  observationsList: document.getElementById('observationsList'),
  rsRootCause: document.getElementById('rsRootCause'),
  recCount: document.getElementById('recCount'),
  recImmediate: document.getElementById('recImmediate'),
  recShortTerm: document.getElementById('recShortTerm'),
  recLongTerm: document.getElementById('recLongTerm'),
  recPreventive: document.getElementById('recPreventive'),
  conflictsSection: document.getElementById('conflictsSection'),
  conflictCount: document.getElementById('conflictCount'),
  conflictsList: document.getElementById('conflictsList'),
  missingSection: document.getElementById('missingSection'),
  missingCount: document.getElementById('missingCount'),
  missingList: document.getElementById('missingList'),

  // Download
  downloadPDF: document.getElementById('downloadPDF'),
  downloadJSON: document.getElementById('downloadJSON'),
  downloadMeta: document.getElementById('downloadMeta'),
  newReportBtn: document.getElementById('newReportBtn'),
});

/* ============================================================
   STATE MANAGER
   ============================================================ */

class StateManager {
  #state = {
    inspectionFile: null,
    thermalFile: null,
    lastResult: null,
    isProcessing: false,
    processingStartTime: null,
    processedCount: parseInt(localStorage.getItem('ddr_processed_count')) || 0,
    totalProcessingTime: parseFloat(localStorage.getItem('ddr_total_time')) || 0,
  };

  #listeners = new Map();

  /**
   * Get current state value
   * @param {string} key - State key
   * @returns {*} State value
   */
  get(key) {
    return this.#state[key];
  }

  /**
   * Set state value with change notification
   * @param {string} key - State key
   * @param {*} value - New value
   * @param {boolean} silent - Skip notifications
   */
  set(key, value, silent = false) {
    const oldValue = this.#state[key];
    this.#state[key] = value;

    // Persist metrics
    if (key === 'processedCount') {
      localStorage.setItem('ddr_processed_count', String(value));
    }
    if (key === 'totalProcessingTime') {
      localStorage.setItem('ddr_total_time', String(value));
    }

    if (!silent && this.#listeners.has(key)) {
      for (const listener of this.#listeners.get(key)) {
        listener(value, oldValue);
      }
    }
  }

  /**
   * Subscribe to state changes
   * @param {string} key - State key
   * @param {Function} listener - Callback function
   */
  subscribe(key, listener) {
    if (!this.#listeners.has(key)) {
      this.#listeners.set(key, new Set());
    }
    this.#listeners.get(key).add(listener);
  }

  /**
   * Unsubscribe from state changes
   * @param {string} key - State key
   * @param {Function} listener - Callback function
   */
  unsubscribe(key, listener) {
    if (this.#listeners.has(key)) {
      this.#listeners.get(key).delete(listener);
    }
  }

  /**
   * Reset application state
   */
  reset() {
    this.#state.inspectionFile = null;
    this.#state.thermalFile = null;
    this.#state.lastResult = null;
    this.#state.isProcessing = false;
    this.#state.processingStartTime = null;
  }
}

const state = new StateManager();

/* ============================================================
   UTILITY FUNCTIONS
   ============================================================ */

const Utils = {
  /**
   * Format bytes to human-readable string
   * @param {number} bytes - Bytes to format
   * @returns {string} Formatted size
   */
  formatBytes(bytes) {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  },

  /**
   * Generate unique ID
   * @returns {string} Unique ID
   */
  generateId() {
    return Date.now().toString(36) + Math.random().toString(36).substring(2, 8);
  },

  /**
   * Format date for display
   * @param {Date|string} date - Date to format
   * @returns {string} Formatted date
   */
  formatDate(date) {
    const d = date instanceof Date ? date : new Date(date);
    return d.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  },

  /**
   * Escape HTML in string
   * @param {string} str - String to escape
   * @returns {string} Escaped string
   */
  escapeHtml(str) {
    if (!str) return '';
    const el = document.createElement('div');
    el.textContent = str;
    return el.innerHTML;
  },

  /**
   * Format a Date as YYYY-MM-DD for filenames
   * @param {Date} [date] - Date to format (defaults to now)
   * @returns {string} Formatted timestamp
   */
  fileTimestamp(date = new Date()) {
    return [
      date.getFullYear(),
      String(date.getMonth() + 1).padStart(2, '0'),
      String(date.getDate()).padStart(2, '0'),
    ].join('-');
  },

  /**
   * Debounce function
   * @param {Function} fn - Function to debounce
   * @param {number} delay - Delay in milliseconds
   * @returns {Function} Debounced function
   */
  debounce(fn, delay = 300) {
    let timeoutId;
    return function(...args) {
      clearTimeout(timeoutId);
      timeoutId = setTimeout(() => fn.apply(this, args), delay);
    };
  },

  /**
   * Throttle function
   * @param {Function} fn - Function to throttle
   * @param {number} limit - Limit in milliseconds
   * @returns {Function} Throttled function
   */
  throttle(fn, limit = 100) {
    let inThrottle;
    return function(...args) {
      if (!inThrottle) {
        fn.apply(this, args);
        inThrottle = setTimeout(() => inThrottle = false, limit);
      }
    };
  },

  /**
   * Safely get nested property
   * @param {Object} obj - Object to search
   * @param {string} path - Dot notation path
   * @param {*} defaultValue - Default value if not found
   * @returns {*} Value at path or default
   */
  safeGet(obj, path, defaultValue = null) {
    try {
      return path.split('.').reduce((current, key) => current?.[key], obj) ?? defaultValue;
    } catch {
      return defaultValue;
    }
  }
};

/* ============================================================
   VALIDATION ENGINE
   ============================================================ */

class ValidationEngine {
  /**
   * Validate a file
   * @param {File} file - File to validate
   * @returns {Object} Validation result
   */
  validateFile(file) {
    if (!file) {
      return { ok: false, error: 'No file selected.' };
    }

    if (file.type !== CONFIG.ACCEPTED_TYPE && !file.name.toLowerCase().endsWith('.pdf')) {
      return { ok: false, error: `${file.name} is not a PDF.` };
    }

    if (file.size > CONFIG.MAX_FILE_SIZE_MB * 1024 * 1024) {
      return {
        ok: false,
        error: `File exceeds ${CONFIG.MAX_FILE_SIZE_MB} MB limit.`
      };
    }

    return { ok: true };
  }

  /**
   * Check for duplicate file
   * @param {File} file - File to check
   * @param {File} existingFile - Existing file
   * @returns {boolean} True if duplicate
   */
  isDuplicate(file, existingFile) {
    if (!existingFile) return false;
    return file.name === existingFile.name && file.size === existingFile.size;
  }
}

const validator = new ValidationEngine();

/* ============================================================
   UPLOAD MANAGER
   ============================================================ */

class UploadManager {
  #initialized = false;

  constructor() {
    if (this.#initialized) return;
    this.#initialized = true;

    this.#bindEvents();
    this.#setupDragDrop();
    this.#setupStateSubscriptions();
  }

  #bindEvents() {
    // File input changes
    DOM.inspectionFile.addEventListener('change', (e) => {
      const file = e.target.files?.[0];
      if (file) this.#handleFile('inspection', file);
    });

    DOM.thermalFile.addEventListener('change', (e) => {
      const file = e.target.files?.[0];
      if (file) this.#handleFile('thermal', file);
    });

    // Remove buttons
    DOM.inspectionRemove.addEventListener('click', (e) => {
      e.stopPropagation();
      this.removeFile('inspection');
    });

    DOM.thermalRemove.addEventListener('click', (e) => {
      e.stopPropagation();
      this.removeFile('thermal');
    });

    // Keyboard activation
    DOM.inspectionZone.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        DOM.inspectionFile.click();
      }
    });

    DOM.thermalZone.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        DOM.thermalFile.click();
      }
    });
  }

  #setupDragDrop() {
    const zones = [
      { zone: DOM.inspectionZone, type: 'inspection' },
      { zone: DOM.thermalZone, type: 'thermal' },
    ];

    for (const { zone, type } of zones) {
      zone.addEventListener('dragenter', (e) => {
        e.preventDefault();
        zone.classList.add('drag-over');
      });

      zone.addEventListener('dragover', (e) => {
        e.preventDefault();
        zone.classList.add('drag-over');
      });

      zone.addEventListener('dragleave', (e) => {
        if (!zone.contains(e.relatedTarget)) {
          zone.classList.remove('drag-over');
        }
      });

      zone.addEventListener('drop', (e) => {
        e.preventDefault();
        zone.classList.remove('drag-over');
        const file = e.dataTransfer?.files?.[0];
        if (file) this.#handleFile(type, file);
      });
    }
  }

  #setupStateSubscriptions() {
    state.subscribe('inspectionFile', () => this.#updateUI());
    state.subscribe('thermalFile', () => this.#updateUI());
  }

  #handleFile(type, file) {
    const validation = validator.validateFile(file);

    if (!validation.ok) {
      this.#showError(type, validation.error);
      return;
    }

    const existing = state.get(`${type}File`);
    if (validator.isDuplicate(file, existing)) {
      this.#showError(type, 'This file is already uploaded.');
      return;
    }

    state.set(`${type}File`, file);
    this.#updateFileUI(type, file);
    this.#updateUI();
  }

  /**
   * Remove an uploaded file and reset its zone UI.
   * Public so other modules (e.g. DownloadManager's "New report" reset) can call it.
   * @param {'inspection'|'thermal'} type
   */
  removeFile(type) {
    state.set(`${type}File`, null);

    const zone = type === 'inspection' ? DOM.inspectionZone : DOM.thermalZone;
    const info = type === 'inspection' ? DOM.inspectionInfo : DOM.thermalInfo;
    const input = type === 'inspection' ? DOM.inspectionFile : DOM.thermalFile;

    zone.classList.remove('has-file', 'has-error', 'drag-over');
    info.hidden = true;
    input.value = '';

    this.#updateUI();
  }

  #updateFileUI(type, file) {
    const zone = type === 'inspection' ? DOM.inspectionZone : DOM.thermalZone;
    const info = type === 'inspection' ? DOM.inspectionInfo : DOM.thermalInfo;
    const nameEl = type === 'inspection' ? DOM.inspectionName : DOM.thermalName;
    const sizeEl = type === 'inspection' ? DOM.inspectionSize : DOM.thermalSize;
    const statusEl = type === 'inspection' ? DOM.inspectionStatus : DOM.thermalStatus;

    zone.classList.remove('drag-over', 'has-error');
    zone.classList.add('has-file');

    nameEl.textContent = file.name;
    sizeEl.textContent = Utils.formatBytes(file.size);
    statusEl.textContent = '✓ Ready';
    statusEl.style.color = 'var(--accent-emerald)';

    info.hidden = false;
  }

  #showError(type, message) {
    const zone = type === 'inspection' ? DOM.inspectionZone : DOM.thermalZone;
    zone.classList.remove('drag-over', 'has-file');
    zone.classList.add('has-error');

    // Show error on status
    const statusEl = type === 'inspection' ? DOM.inspectionStatus : DOM.thermalStatus;
    statusEl.textContent = `✕ ${message}`;
    statusEl.style.color = 'var(--sev-critical)';

    setTimeout(() => {
      zone.classList.remove('has-error');
      statusEl.textContent = '—';
      statusEl.style.color = '';
    }, 3000);

    console.warn('[Upload]', message);
  }

  #updateUI() {
    const hasInspection = !!state.get('inspectionFile');
    const hasThermal = !!state.get('thermalFile');
    const ready = hasInspection && hasThermal;

    DOM.generateBtn.disabled = !ready || state.get('isProcessing');
    DOM.generateBtn.querySelector('.btn-generate-label').textContent = ready
      ? 'Generate DDR Report'
      : 'Generate DDR Report';

    // Update nav status
    if (ready) {
      this.#setStatus('ready', 'Files ready');
    } else if (hasInspection || hasThermal) {
      this.#setStatus('idle', 'Waiting for second file');
    } else {
      this.#setStatus('idle', 'Ready');
    }
  }

  #setStatus(statusState, text) {
    const dot = DOM.statusDot;
    dot.className = 'status-dot';

    const states = {
      idle: 'status-dot--idle',
      ready: 'status-dot--ready',
      working: 'status-dot--working',
      done: 'status-dot--done',
      error: 'status-dot--error',
    };

    if (states[statusState]) dot.classList.add(states[statusState]);

    DOM.statusText.textContent = text;
  }
}

const uploadManager = new UploadManager();

/* ============================================================
   API CLIENT
   ============================================================ */

class APIClient {
  #retryCount = 0;
  #maxRetries = 3;

  /**
   * Generate DDR report.
   * Sends the two PDFs as multipart/form-data, matching the backend's
   * /generate-ddr endpoint which expects `inspection_report` and
   * `thermal_report` binary fields (NOT base64 JSON).
   * @param {File} inspectionFile - Inspection report
   * @param {File} thermalFile - Thermal report
   * @returns {Promise<Object>} DDR report data
   */
  async generate(inspectionFile, thermalFile) {
    this.#retryCount = 0;

    const formData = new FormData();
    formData.append('inspection_report', inspectionFile, inspectionFile.name);
    formData.append('thermal_report', thermalFile, thermalFile.name);

    return this.#callAPI(formData);
  }

  async #callAPI(formData) {
    try {
      if (ENV.isDevelopment) {
        console.log(`%c[API] POST ${CONFIG.API_ENDPOINT}`, 'color: #FF9800;');
      }

      const response = await fetch(CONFIG.API_ENDPOINT, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        const message = this.#extractErrorMessage(errorData, response.status);
        throw new Error(message);
      }

      const result = await response.json();

      if (ENV.isDevelopment) {
        console.log('%c[API] Response received', 'color: #4CAF50;');
        // Log the full response structure
        console.log('Response keys:', Object.keys(result));
        console.log('Response preview:', JSON.stringify(result, null, 2).substring(0, 1000));
      }

      return result;
    } catch (error) {
      if (ENV.isDevelopment) {
        console.error('%c[API] Error:', 'color: #F44336;', error.message);
      }

      if (this.#retryCount < this.#maxRetries && this.#shouldRetry(error)) {
        this.#retryCount++;
        const delay = 1000 * this.#retryCount;
        console.warn(`[API] Retrying in ${delay}ms (attempt ${this.#retryCount}/${this.#maxRetries})`);
        await this.#delay(delay);
        return this.#callAPI(formData);
      }
      throw error;
    }
  }

  /**
   * Extract a human-readable error message, including FastAPI's
   * 422 validation error shape: { detail: [{ loc, msg, type }] }
   */
  #extractErrorMessage(errorData, status) {
    if (Array.isArray(errorData?.detail)) {
      return errorData.detail
        .map((d) => `${(d.loc || []).join('.')}: ${d.msg}`)
        .join('; ') || `Validation error (${status})`;
    }
    if (typeof errorData?.detail === 'string') {
      return errorData.detail;
    }
    return errorData?.message || errorData?.error || `Server error (${status})`;
  }

  #shouldRetry(error) {
    // Retry on network errors or 5xx responses
    return error.message.includes('fetch') ||
           error.message.includes('network') ||
           error.message.includes('500') ||
           error.message.includes('502') ||
           error.message.includes('503');
  }

  #delay(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}

const apiClient = new APIClient();

/* ============================================================
   PROCESSING ENGINE
   ============================================================ */

class ProcessingEngine {
  #stepElements = [];
  #currentStep = -1;
  #intervalId = null;
  #startTime = null;

  constructor() {
    this.#buildSteps();
  }

  #buildSteps() {
    DOM.processingSteps.innerHTML = '';

    this.#stepElements = CONFIG.STEPS.map((step) => {
      const el = document.createElement('div');
      el.className = 'ps-step';
      el.setAttribute('data-step', step.id);
      el.innerHTML = `
        <div class="ps-dot" role="img" aria-label="${step.label} status"></div>
        <div class="ps-content">
          <span class="ps-label">${step.label}</span>
          <span class="ps-description">${step.description}</span>
        </div>
        <span class="ps-status"></span>
      `;
      DOM.processingSteps.appendChild(el);
      return el;
    });
  }

  /**
   * Start processing simulation
   */
  start() {
    this.#startTime = Date.now();
    this.#currentStep = -1;

    DOM.processingPanel.hidden = false;
    DOM.processingTitle.textContent = 'Initializing AI Pipeline';
    DOM.processingSubtitle.textContent = 'Preparing neural processing engines';

    this.#advanceStep();

    // Simulate steps with realistic timing
    this.#intervalId = setInterval(() => {
      if (this.#currentStep < CONFIG.STEPS.length - 1) {
        this.#advanceStep();
      } else {
        clearInterval(this.#intervalId);
        this.#intervalId = null;
      }
    }, 1800);
  }

  #advanceStep() {
    this.#currentStep++;
    const step = CONFIG.STEPS[this.#currentStep];

    // Update step UI
    this.#stepElements.forEach((el, i) => {
      el.classList.remove('active', 'done');
      if (i < this.#currentStep) el.classList.add('done');
      else if (i === this.#currentStep) el.classList.add('active');
    });

    // Update progress
    const progress = ((this.#currentStep + 1) / CONFIG.STEPS.length) * 100;
    DOM.progressBar.style.width = `${progress}%`;
    DOM.progressBar.setAttribute('aria-valuenow', progress);
    DOM.processingProgress.textContent = Math.round(progress);

    // Update title
    DOM.processingTitle.textContent = step.label;
    DOM.processingSubtitle.textContent = step.description;

    // Update step status
    const statusEl = this.#stepElements[this.#currentStep].querySelector('.ps-status');
    if (this.#currentStep === CONFIG.STEPS.length - 1) {
      statusEl.textContent = '✓';
      statusEl.style.color = 'var(--accent-emerald)';
    } else {
      statusEl.textContent = '●';
      statusEl.style.color = 'var(--accent-primary)';
    }

    // Update time
    const elapsed = ((Date.now() - this.#startTime) / 1000).toFixed(1);
    DOM.processingTime.textContent = elapsed;
  }

  /**
   * Complete processing
   */
  complete() {
    if (this.#intervalId) {
      clearInterval(this.#intervalId);
      this.#intervalId = null;
    }

    // Mark all steps as done
    this.#stepElements.forEach((el) => {
      el.classList.remove('active');
      el.classList.add('done');
    });

    DOM.progressBar.style.width = '100%';
    DOM.progressBar.setAttribute('aria-valuenow', 100);
    DOM.processingProgress.textContent = '100';
    DOM.processingTitle.textContent = 'Report generated successfully';
    DOM.processingSubtitle.textContent = 'DDR report ready for review';

    // Update final time
    const elapsed = ((Date.now() - this.#startTime) / 1000).toFixed(1);
    DOM.processingTime.textContent = elapsed;
  }

  /**
   * Reset processing state
   */
  reset() {
    if (this.#intervalId) {
      clearInterval(this.#intervalId);
      this.#intervalId = null;
    }

    this.#stepElements.forEach((el) => {
      el.classList.remove('active', 'done');
    });

    DOM.progressBar.style.width = '0%';
    DOM.progressBar.setAttribute('aria-valuenow', 0);
    DOM.processingProgress.textContent = '0';
    DOM.processingTime.textContent = '0';
    DOM.processingTitle.textContent = 'Initializing AI Pipeline';
    DOM.processingSubtitle.textContent = 'Preparing neural processing engines';
    DOM.processingPanel.hidden = true;
  }
}

const processingEngine = new ProcessingEngine();

/* ============================================================
   RESULTS RENDERER - FIXED normalization logic
   ============================================================ */

class ResultsRenderer {
  /**
   * Render report results
   * @param {Object} data - Report data from API
   */
  render(data) {
    // Comprehensive debug logging - log the full JSON response
    console.log('%c========== FULL API RESPONSE ==========', 'color: #FF6B6B; font-weight: bold; font-size: 14px;');
    console.log(JSON.stringify(data, null, 2));
    console.log('%c=========================================', 'color: #FF6B6B; font-weight: bold;');
    
    // Log specific fields we care about
    console.log('📋 Response keys:', Object.keys(data));
    console.log('📊 Observations:', data.area_observations || data.observations || 'NOT FOUND');
    console.log('📈 Recommendations:', data.recommendations || data.recommended_actions || 'NOT FOUND');
    console.log('🎯 Confidence Score:', data.confidence_score || data.confidence_metrics?.overall_confidence || 'NOT FOUND');
    console.log('🔍 Root Cause:', data.root_cause || data.root_cause_analysis || 'NOT FOUND');
    console.log('⚡ Conflicts:', data.conflicts || 'NOT FOUND');
    
    // Normalize data - handle both flat and nested structures
    const normalizedData = this.#normalizeData(data);
    
    // Log what we're actually using
    console.log('📦 Normalized data keys:', Object.keys(normalizedData));
    console.log('📊 Normalized observations count:', normalizedData.area_observations?.length || 0);
    console.log('🎯 Normalized confidence:', normalizedData.confidence_score);
    
    // Update metrics
    this.#renderMetrics(normalizedData);

    // Update sections
    this.#renderSummary(normalizedData);
    this.#renderAnalytics(normalizedData);
    this.#renderObservations(normalizedData);
    this.#renderRootCause(normalizedData);
    this.#renderRecommendations(normalizedData);
    this.#renderConflicts(normalizedData);
    this.#renderMissing(normalizedData);
    this.#renderDownload(normalizedData);

    // Update dashboard
    DOM.dashboardReportId.textContent = normalizedData.report_id || 'DDR-2025-001';
    DOM.dashboardTimestamp.textContent = Utils.formatDate(normalizedData.generated_at || new Date());
    DOM.dashboardBadge.textContent = '✓ Report Ready';
    DOM.dashboardBadge.style.color = 'var(--accent-emerald)';

    // Show results
    DOM.resultsPanel.hidden = false;
    state.set('lastResult', normalizedData);
    this.#setStatus('done', 'Report ready');

    // Update hero stats
    const processed = state.get('processedCount') + 1;
    state.set('processedCount', processed);
    DOM.processedCount.textContent = processed;

    // Update average time
    const processingTime = normalizedData.processing_metadata?.duration_seconds || normalizedData.processing_time || 0;
    const totalTime = state.get('totalProcessingTime') + processingTime;
    state.set('totalProcessingTime', totalTime);
    const avgTime = (totalTime / processed).toFixed(1);
    DOM.avgTime.textContent = `${avgTime}s`;
  }

  /**
   * Normalize data from various response formats
   * FIXED: Properly checks if data.data has actual content before using it
   */
  #normalizeData(data) {
    // Debug logging to see what we're working with
    console.log('🔍 ROOT DATA:', data);
    console.log('🔍 NESTED DATA (data.data):', data.data);
    
    // Determine which data source to use
    // Only use data.data if it exists AND has meaningful content
    let raw;
    const nestedData = data.data;
    
    // Check if nested data exists and has actual content (not just an empty object)
    const hasNestedContent = nestedData && 
                           typeof nestedData === 'object' && 
                           Object.keys(nestedData).length > 0;
    
    // Check if root has the data we need
    const rootHasData = data.area_observations || 
                       data.confidence_score !== undefined ||
                       data.recommendations ||
                       data.root_cause;
    
    // If nested has content, use it; otherwise use root
    if (hasNestedContent && !rootHasData) {
      raw = nestedData;
      console.log('✅ Using NESTED data (has content)');
    } else {
      raw = data;
      console.log('✅ Using ROOT data (has content)');
    }
    
    console.log('📦 USING raw data keys:', Object.keys(raw));
    
    // Ensure all fields exist with defaults
    return {
      // Core fields
      property_summary: raw.property_summary || '',
      area_observations: raw.area_observations || raw.observations || [],
      observations: raw.observations || raw.area_observations || [],
      
      // Root cause
      root_cause: raw.root_cause || '',
      root_cause_analysis: raw.root_cause_analysis || {
        primary_cause: raw.root_cause || 'Unable to determine root cause from available data.',
        supporting_evidence: [],
        reasoning_chain: [],
        contributing_factors: [],
        confidence: 0.0
      },
      
      // Recommendations
      recommendations: raw.recommendations || [],
      recommended_actions: raw.recommended_actions || [],
      
      // Conflicts
      conflicts: raw.conflicts || [],
      
      // Severity
      severity_assessment: raw.severity_assessment || {
        overall_severity: 'info',
        average_score: 0.0,
        distribution: {}
      },
      
      // Confidence
      confidence_score: raw.confidence_score ?? raw.confidence_metrics?.overall_confidence ?? 0,
      confidence_metrics: raw.confidence_metrics || {
        overall_confidence: raw.confidence_score || 0,
        evidence_quality: 0,
        data_completeness: 0,
        reasoning_confidence: 0,
        conflict_density: 0,
        observation_quality: 0
      },
      
      // Executive summary
      executive_summary: raw.executive_summary || {
        key_findings: [],
        risk_overview: 'No critical or high severity issues identified.',
        critical_observations: [],
        property_health_score: 100,
        overall_recommendations: [],
        major_concerns: [],
        quick_wins: [],
        long_term_strategies: []
      },
      
      // Missing information
      missing_information: raw.missing_information || [],
      
      // Metadata
      processing_metadata: raw.processing_metadata || {},
      processing_time: raw.processing_time || 0,
      report_id: raw.report_id || 'DDR-2025-001',
      generated_at: raw.generated_at || new Date().toISOString(),
      pdf_url: raw.pdf_url || null,
      pdf_base64: raw.pdf_base64 || null,
      pages: raw.pages || '—',
      
      // Preserve original data
      _original: raw
    };
  }

  /**
   * Build the download filename timestamp.
   * Public wrapper around Utils.fileTimestamp so other modules
   * (e.g. DownloadManager) can reuse the exact same naming convention.
   */
  timestamp() {
    return Utils.fileTimestamp();
  }

  #renderMetrics(data) {
    // Get observations count
    const observations = this.#getObservations(data);
    
    DOM.smAreas.textContent = observations.length || '—';
    
    // Get severity from severity_assessment or calculate from observations
    let severity = data.severity_assessment?.overall_severity || '—';
    if (severity === '—' && observations.length > 0) {
      const critical = observations.filter(o => 
        (o.severity || '').toLowerCase() === 'critical'
      ).length;
      const high = observations.filter(o => 
        (o.severity || '').toLowerCase() === 'high'
      ).length;
      if (critical > 0) severity = 'Critical';
      else if (high > 0) severity = 'High';
      else severity = 'Medium';
    }
    DOM.smSeverity.textContent = severity;
    
    // Get recommendations count
    const recommendations = data.recommendations || data.recommended_actions || [];
    DOM.smActions.textContent = recommendations.length || '—';

    // Get confidence from various possible locations
    const confidence = data.confidence_score ?? 
                       data.confidence_metrics?.overall_confidence ?? 
                       0;
    DOM.smConfidence.textContent = `${Math.round(confidence * 100)}%`;

    // Update confidence ring
    const circumference = 2 * Math.PI * 25;
    const offset = circumference - (confidence * circumference);
    DOM.confidenceFill.style.strokeDashoffset = offset;
  }

  #renderSummary(data) {
    const summary = data.executive_summary || {};
    const propertySummary = data.property_summary || '';
    
    // Build summary text from various possible formats
    let summaryText = '';
    if (propertySummary) {
      summaryText = propertySummary;
    } else if (typeof summary === 'string') {
      summaryText = summary;
    } else if (summary.key_findings && Array.isArray(summary.key_findings)) {
      summaryText = summary.key_findings.join('. ');
    } else if (summary.risk_overview) {
      summaryText = summary.risk_overview;
    } else if (summary.overall_recommendations && Array.isArray(summary.overall_recommendations)) {
      summaryText = summary.overall_recommendations.join('. ');
    } else {
      summaryText = 'No executive summary available.';
    }
    
    DOM.rsSummary.innerHTML = `<p class="rs-summary-text">${Utils.escapeHtml(summaryText)}</p>`;
  }

  #renderAnalytics(data) {
    const observations = this.#getObservations(data);

    const counts = {
      critical: 0,
      high: 0,
      medium: 0,
      low: 0,
    };

    for (const obs of observations) {
      const severity = (obs.severity || 'info').toLowerCase();
      if (counts[severity] !== undefined) counts[severity]++;
    }

    const total = observations.length || 1;

    DOM.analyticsCritical.textContent = counts.critical;
    DOM.analyticsHigh.textContent = counts.high;
    DOM.analyticsMedium.textContent = counts.medium;
    DOM.analyticsLow.textContent = counts.low;

    // Update bars
    document.querySelectorAll('.analytics-bar-fill').forEach((bar, index) => {
      const values = [counts.critical, counts.high, counts.medium, counts.low];
      const percent = (values[index] / total) * 100;
      bar.style.width = `${percent}%`;
    });
  }

  #renderObservations(data) {
    const observations = this.#getObservations(data);
    DOM.obsCount.textContent = `${observations.length} findings`;
    DOM.observationsList.innerHTML = '';

    if (observations.length === 0) {
      DOM.observationsList.innerHTML = `
        <div class="obs-card">
          <div class="obs-content">
            <div class="obs-area">No observations</div>
            <div class="obs-description">No observations were extracted from the reports.</div>
          </div>
        </div>
      `;
      return;
    }

    for (const obs of observations) {
      const severity = (obs.severity || 'info').toLowerCase();
      const card = document.createElement('div');
      card.className = 'obs-card';
      
      // Get observation text from various possible fields
      const obsText = obs.observation || obs.description || obs.text || '';
      const area = obs.area || 'Unnamed Area';
      
      // Build evidence text
      let evidenceText = '';
      if (obs.evidence && obs.evidence.length > 0) {
        evidenceText = obs.evidence.map(e => 
          typeof e === 'string' ? e : (e.text || e.description || '')
        ).join('; ');
      }
      
      // Build severity class
      const severityClass = severity === 'critical' ? 'obs-severity--critical' :
                            severity === 'high' ? 'obs-severity--high' :
                            severity === 'medium' ? 'obs-severity--medium' :
                            'obs-severity--low';
      
      card.innerHTML = `
        <span class="obs-severity ${severityClass}" aria-label="Severity: ${severity}">
          ${severity}
        </span>
        <div class="obs-content">
          <div class="obs-area">${Utils.escapeHtml(area)}</div>
          <div class="obs-description">${Utils.escapeHtml(obsText)}</div>
          ${evidenceText ? `<div class="obs-evidence">📎 ${Utils.escapeHtml(evidenceText)}</div>` : ''}
          ${obs.category ? `<div class="obs-category">🏷️ ${Utils.escapeHtml(obs.category)}</div>` : ''}
        </div>
      `;
      DOM.observationsList.appendChild(card);
    }
  }

  #renderRootCause(data) {
    const rootCause = data.root_cause_analysis || {};
    let rootCauseHtml = '';
    
    if (typeof rootCause === 'string') {
      rootCauseHtml = Utils.escapeHtml(rootCause);
    } else if (rootCause.primary_cause) {
      rootCauseHtml = `<strong>Primary Cause:</strong> ${Utils.escapeHtml(rootCause.primary_cause)}`;
      
      if (rootCause.supporting_evidence && rootCause.supporting_evidence.length > 0) {
        rootCauseHtml += `<br><br><strong>Supporting Evidence:</strong><br>`;
        rootCauseHtml += rootCause.supporting_evidence.map(e => `• ${Utils.escapeHtml(e)}`).join('<br>');
      }
      
      if (rootCause.reasoning_chain && rootCause.reasoning_chain.length > 0) {
        rootCauseHtml += `<br><br><strong>Reasoning Chain:</strong><br>`;
        rootCauseHtml += rootCause.reasoning_chain.map(r => `• ${Utils.escapeHtml(r)}`).join('<br>');
      }
      
      if (rootCause.contributing_factors && rootCause.contributing_factors.length > 0) {
        rootCauseHtml += `<br><br><strong>Contributing Factors:</strong><br>`;
        rootCauseHtml += rootCause.contributing_factors.map(f => `• ${Utils.escapeHtml(f)}`).join('<br>');
      }
      
      if (rootCause.confidence !== undefined) {
        rootCauseHtml += `<br><br><strong>Confidence:</strong> ${Math.round(rootCause.confidence * 100)}%`;
      }
    } else {
      rootCauseHtml = data.root_cause || 'Unable to determine root cause from available data.';
    }
    
    DOM.rsRootCause.innerHTML = `<div class="rs-root-cause-text">${rootCauseHtml}</div>`;
  }

  #renderRecommendations(data) {
    // Try multiple sources for recommendations
    let recommendations = data.recommendations || data.recommended_actions || [];
    
    // If recommendations is an array of strings, convert to objects
    if (recommendations.length > 0 && typeof recommendations[0] === 'string') {
      recommendations = recommendations.map(action => ({
        action: action,
        priority: 'short-term',
        category: 'General'
      }));
    }
    
    DOM.recCount.textContent = `${recommendations.length} actions`;

    // Clear all groups
    DOM.recImmediate.innerHTML = '';
    DOM.recShortTerm.innerHTML = '';
    DOM.recLongTerm.innerHTML = '';
    DOM.recPreventive.innerHTML = '';

    if (recommendations.length === 0) {
      DOM.recImmediate.innerHTML = `
        <li class="rec-item">No recommendations available.</li>
      `;
      return;
    }

    // Group recommendations
    const groups = {
      immediate: [],
      'short-term': [],
      'long-term': [],
      preventive: [],
    };

    for (const rec of recommendations) {
      const priority = (rec.priority || 'short-term').toLowerCase();
      const text = typeof rec === 'string' ? rec : (rec.action || rec.description || '');

      if (groups[priority]) {
        groups[priority].push(text);
      } else {
        groups['short-term'].push(text);
      }
    }

    // Render each group
    const renderGroup = (list, items) => {
      if (items.length === 0) {
        list.innerHTML = '<li class="rec-item">No actions in this category.</li>';
        return;
      }

      for (const item of items) {
        const li = document.createElement('li');
        li.className = 'rec-item';
        li.textContent = item;
        list.appendChild(li);
      }
    };

    renderGroup(DOM.recImmediate, groups.immediate);
    renderGroup(DOM.recShortTerm, groups['short-term']);
    renderGroup(DOM.recLongTerm, groups['long-term']);
    renderGroup(DOM.recPreventive, groups.preventive);
  }

  #renderConflicts(data) {
    const conflicts = data.conflicts || [];
    DOM.conflictCount.textContent = `${conflicts.length} conflicts`;

    if (conflicts.length === 0) {
      DOM.conflictsSection.hidden = true;
      return;
    }

    DOM.conflictsSection.hidden = false;
    DOM.conflictsList.innerHTML = '';

    for (const conflict of conflicts) {
      const div = document.createElement('div');
      div.className = 'conflict-item';

      const description = typeof conflict === 'string'
        ? conflict
        : (conflict.description || conflict.message || '');

      const severity = (conflict.severity || 'medium').toLowerCase();
      const severityClass = severity === 'high' || severity === 'critical'
        ? 'conflict-severity--high'
        : 'conflict-severity--medium';

      div.innerHTML = `
        <div>
          <div>${Utils.escapeHtml(description)}</div>
          ${conflict.conflict_type || conflict.type ? 
            `<div class="conflict-severity ${severityClass}">${conflict.conflict_type || conflict.type}</div>` : 
            ''}
        </div>
      `;

      DOM.conflictsList.appendChild(div);
    }
  }

  #renderMissing(data) {
    const missing = data.missing_information || [];
    DOM.missingCount.textContent = `${missing.length} items`;

    if (missing.length === 0) {
      DOM.missingSection.hidden = true;
      return;
    }

    DOM.missingSection.hidden = false;
    DOM.missingList.innerHTML = '';

    for (const item of missing) {
      const li = document.createElement('li');
      li.className = 'missing-item';
      li.textContent = typeof item === 'string' ? item : (item.field || item.message || '');
      DOM.missingList.appendChild(li);
    }
  }

  #renderDownload(data) {
    // PDF download — supports either an inline base64 PDF or a download URL
    if (data.pdf_base64) {
      const blob = this.#base64ToBlob(data.pdf_base64, 'application/pdf');
      const url = URL.createObjectURL(blob);
      DOM.downloadPDF.href = url;
      DOM.downloadPDF.download = `DDR_Report_${this.timestamp()}.pdf`;
      DOM.downloadPDF.style.display = 'inline-flex';
    } else if (data.pdf_url) {
      const href = data.pdf_url.startsWith('http') ? data.pdf_url : `${CONFIG.API_BASE_URL}${data.pdf_url}`;
      DOM.downloadPDF.href = href;
      DOM.downloadPDF.removeAttribute('download');
      DOM.downloadPDF.target = '_blank';
      DOM.downloadPDF.rel = 'noopener noreferrer';
      DOM.downloadPDF.style.display = 'inline-flex';
    } else {
      DOM.downloadPDF.style.display = 'none';
    }

    // Update metadata
    const processingTime = data.processing_metadata?.duration_seconds || data.processing_time || 0;
    const pages = data.pages || '—';
    DOM.downloadMeta.textContent = `Generated in ${processingTime.toFixed(1)}s · ${pages} pages`;
  }

  /**
   * Helper method to get observations from various possible locations in the response
   */
  #getObservations(data) {
    // Try multiple possible field names
    const obs = data.area_observations || 
                data.observations || 
                data.findings || 
                data.areaObservations || 
                [];
    
    // If we got an array, return it
    if (Array.isArray(obs)) {
      return obs;
    }
    
    // If it's an object with an observations array inside
    if (obs && typeof obs === 'object' && obs.observations && Array.isArray(obs.observations)) {
      return obs.observations;
    }
    
    return [];
  }

  #base64ToBlob(b64, mime) {
    const bytes = atob(b64);
    const arr = new Uint8Array(bytes.length);
    for (let i = 0; i < bytes.length; i++) {
      arr[i] = bytes.charCodeAt(i);
    }
    return new Blob([arr], { type: mime });
  }

  #setStatus(statusState, text) {
    const dot = DOM.statusDot;
    dot.className = 'status-dot';

    const states = {
      idle: 'status-dot--idle',
      ready: 'status-dot--ready',
      working: 'status-dot--working',
      done: 'status-dot--done',
      error: 'status-dot--error',
    };

    if (states[statusState]) dot.classList.add(states[statusState]);
    DOM.statusText.textContent = text;
  }
}

const resultsRenderer = new ResultsRenderer();

/* ============================================================
   DOWNLOAD MANAGER
   ============================================================ */

class DownloadManager {
  constructor() {
    this.#bindEvents();
  }

  #bindEvents() {
    DOM.downloadJSON.addEventListener('click', () => {
      const data = state.get('lastResult');
      if (!data) return;

      const json = JSON.stringify(data, null, 2);
      const blob = new Blob([json], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `DDR_Report_${resultsRenderer.timestamp()}.json`;
      a.click();
      URL.revokeObjectURL(url);
    });

    DOM.newReportBtn.addEventListener('click', () => {
      this.#reset();
    });
  }

  #reset() {
    // Reset state
    state.reset();

    // Reset UI
    DOM.resultsPanel.hidden = true;
    DOM.errorPanel.hidden = true;
    DOM.processingPanel.hidden = true;

    // Reset uploads
    uploadManager.removeFile('inspection');
    uploadManager.removeFile('thermal');

    // Reset progress
    processingEngine.reset();

    // Scroll to top
    window.scrollTo({ top: 0, behavior: 'smooth' });

    // Update status
    DOM.statusDot.className = 'status-dot status-dot--idle';
    DOM.statusText.textContent = 'Ready';
  }
}

const downloadManager = new DownloadManager();

/* ============================================================
   NOTIFICATION MANAGER
   ============================================================ */

class NotificationManager {
  /**
   * Show a notification
   * @param {string} message - Notification message
   * @param {string} type - Notification type (info, success, warning, error)
   * @param {number} duration - Display duration in milliseconds
   */
  show(message, type = 'info', duration = 4000) {
    const notification = document.createElement('div');
    notification.className = `notification notification--${type}`;
    notification.setAttribute('role', 'alert');
    notification.innerHTML = `
      <span class="notification-icon">${this.#getIcon(type)}</span>
      <span class="notification-message">${Utils.escapeHtml(message)}</span>
    `;

    document.body.appendChild(notification);

    // Trigger animation
    requestAnimationFrame(() => {
      notification.classList.add('notification--visible');
    });

    // Auto-dismiss
    setTimeout(() => {
      notification.classList.remove('notification--visible');
      setTimeout(() => notification.remove(), 300);
    }, duration);
  }

  #getIcon(type) {
    const icons = {
      info: 'ℹ',
      success: '✓',
      warning: '⚠',
      error: '✕',
    };
    return icons[type] || 'ℹ';
  }
}

const notifications = new NotificationManager();

/* ============================================================
   APP CONTROLLER
   ============================================================ */

class AppController {
  #initialized = false;

  constructor() {
    if (this.#initialized) return;
    this.#initialized = true;

    this.#bindEvents();
    this.#setupKeyboardShortcuts();
    this.#restoreMetrics();
  }

  #bindEvents() {
    // Generate button
    DOM.generateBtn.addEventListener('click', () => this.#generate());

    // Retry button
    DOM.retryBtn.addEventListener('click', () => {
      DOM.errorPanel.hidden = true;
      DOM.generateBtn.disabled = false;
      this.#setStatus('ready', 'Files ready');
    });

    // Prevent browser navigation on drag
    document.addEventListener('dragover', (e) => e.preventDefault());
    document.addEventListener('drop', (e) => e.preventDefault());
  }

  #setupKeyboardShortcuts() {
    document.addEventListener('keydown', (e) => {
      // Cmd+Enter or Ctrl+Enter to generate
      if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
        e.preventDefault();
        this.#generate();
      }

      // Cmd+G or Ctrl+G to generate
      if ((e.metaKey || e.ctrlKey) && e.key === 'g') {
        e.preventDefault();
        this.#generate();
      }
    });
  }

  #restoreMetrics() {
    const processed = state.get('processedCount');
    DOM.processedCount.textContent = processed || 0;

    const totalTime = state.get('totalProcessingTime');
    if (totalTime && processed) {
      DOM.avgTime.textContent = `${(totalTime / processed).toFixed(1)}s`;
    }
  }

  async #generate() {
    if (state.get('isProcessing')) return;

    const inspectionFile = state.get('inspectionFile');
    const thermalFile = state.get('thermalFile');

    if (!inspectionFile || !thermalFile) {
      notifications.show('Both reports are required.', 'warning');
      return;
    }

    state.set('isProcessing', true);
    DOM.generateBtn.disabled = true;

    // Update UI for processing
    DOM.errorPanel.hidden = true;
    DOM.resultsPanel.hidden = true;
    this.#setStatus('working', 'Generating report...');

    // Start processing animation
    processingEngine.start();

    try {
      const result = await apiClient.generate(inspectionFile, thermalFile);

      // Complete processing animation
      processingEngine.complete();

      // Small delay for visual polish
      await new Promise((r) => setTimeout(r, 600));

      // Check if result contains the expected data
      const hasObservations = result.area_observations || result.observations;
      const hasRecommendations = result.recommendations || result.recommended_actions;
      
      if (!hasObservations) {
        console.warn('⚠️ No observations found in response. The backend may not be returning the full report data.');
        console.warn('Response keys:', Object.keys(result));
      }

      // Render results
      resultsRenderer.render(result);

      // Show success notification
      const processingTime = result.processing_metadata?.duration_seconds || result.processing_time || 0;
      notifications.show(`Report generated in ${processingTime.toFixed(1)}s`, 'success');

    } catch (error) {
      // Handle error
      processingEngine.reset();

      DOM.errorPanel.hidden = false;
      DOM.errorMessage.textContent = error.message || 'An unexpected error occurred.';
      DOM.errorDetails.textContent = error.stack || '';

      this.#setStatus('error', 'Generation failed');

      notifications.show('Failed to generate report. Please try again.', 'error');
      console.error('[DDR AI] Generation error:', error);

    } finally {
      state.set('isProcessing', false);
      DOM.generateBtn.disabled = !(state.get('inspectionFile') && state.get('thermalFile'));
    }
  }

  #setStatus(statusState, text) {
    const dot = DOM.statusDot;
    dot.className = 'status-dot';

    const states = {
      idle: 'status-dot--idle',
      ready: 'status-dot--ready',
      working: 'status-dot--working',
      done: 'status-dot--done',
      error: 'status-dot--error',
    };

    if (states[statusState]) dot.classList.add(states[statusState]);
    DOM.statusText.textContent = text;
  }
}

/* ============================================================
   BOOT
   ============================================================ */

document.addEventListener('DOMContentLoaded', () => {
  const app = new AppController();

  // Expose for debugging
  if (window.__DDR_DEBUG__) {
    window.__DDR_APP = {
      state,
      uploadManager,
      apiClient,
      processingEngine,
      resultsRenderer,
      notifications,
      app,
      ENV,
      CONFIG,
    };
  }
});