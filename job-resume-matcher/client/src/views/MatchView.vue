<script setup>
import { ref, computed } from 'vue'

// --- State ---
const activeTab = ref('pdf')
const pdfFile = ref(null)
const pdfFilename = ref('')
const resumeText = ref('')
const docsUrl = ref('')
const jobDescription = ref('')

const loading = ref(false)
const streamProgress = ref('')
const error = ref(null)
const result = ref(null)

const isDragging = ref(false)

// --- Computed ---
const canSubmit = computed(() => {
  if (loading.value) return false
  if (!jobDescription.value.trim()) return false
  if (activeTab.value === 'pdf') return pdfFile.value !== null
  if (activeTab.value === 'text') return resumeText.value.trim().length > 0
  if (activeTab.value === 'docs') return docsUrl.value.trim().length > 0
  return false
})

const scoreColor = computed(() => {
  if (!result.value) return '#64748b'
  const s = result.value.overall_score
  if (s >= 70) return '#16a34a'
  if (s >= 50) return '#ca8a04'
  return '#dc2626'
})

const scoreTrackDash = computed(() => {
  if (!result.value) return '0 283'
  const pct = Math.min(100, Math.max(0, result.value.overall_score)) / 100
  return `${(pct * 283).toFixed(1)} 283`
})

const recommendationStyle = computed(() => {
  if (!result.value) return {}
  const map = {
    'strong-match': { bg: '#dcfce7', color: '#15803d', label: 'Strong Match' },
    'good-match': { bg: '#dbeafe', color: '#1d4ed8', label: 'Good Match' },
    'partial-match': { bg: '#fef9c3', color: '#a16207', label: 'Partial Match' },
    'poor-match': { bg: '#fee2e2', color: '#b91c1c', label: 'Poor Match' },
  }
  return map[result.value.recommendation] || { bg: '#f1f5f9', color: '#475569', label: result.value.recommendation }
})

const importanceBadgeStyle = (importance) => {
  const map = {
    'critical': { bg: '#fee2e2', color: '#b91c1c' },
    'important': { bg: '#ffedd5', color: '#c2410c' },
    'nice-to-have': { bg: '#f1f5f9', color: '#475569' },
  }
  return map[importance] || map['nice-to-have']
}

const categoryBadgeStyle = (category) => {
  const map = {
    'technical': { bg: '#dbeafe', color: '#1d4ed8' },
    'behavioral': { bg: '#ede9fe', color: '#6d28d9' },
    'situational': { bg: '#ccfbf1', color: '#0f766e' },
    'gap-probe': { bg: '#ffedd5', color: '#c2410c' },
  }
  return map[category] || { bg: '#f1f5f9', color: '#475569' }
}

// --- File handling ---
const handleFileSelect = (e) => {
  const file = e.target.files[0]
  if (file && file.type === 'application/pdf') {
    pdfFile.value = file
    pdfFilename.value = file.name
  }
}

const handleDrop = (e) => {
  isDragging.value = false
  const file = e.dataTransfer.files[0]
  if (file && file.type === 'application/pdf') {
    pdfFile.value = file
    pdfFilename.value = file.name
  }
}

const handleDragOver = (e) => {
  e.preventDefault()
  isDragging.value = true
}

const handleDragLeave = () => {
  isDragging.value = false
}

const clearFile = () => {
  pdfFile.value = null
  pdfFilename.value = ''
}

// --- Streaming fetch ---
const streamFetch = async (url, options) => {
  const response = await fetch(url, options)
  if (!response.ok) {
    const text = await response.text()
    throw new Error(text || `Server error: ${response.status}`)
  }
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let accumulated = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    const chunk = decoder.decode(value, { stream: true })
    accumulated += chunk
    streamProgress.value = accumulated
  }

  return JSON.parse(accumulated)
}

// --- Submit ---
const analyze = async () => {
  if (!canSubmit.value) return
  loading.value = true
  error.value = null
  result.value = null
  streamProgress.value = ''

  try {
    let data

    if (activeTab.value === 'text') {
      data = await streamFetch('/api/analyze/text', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          resume_text: resumeText.value,
          job_description: jobDescription.value,
        }),
      })
    } else if (activeTab.value === 'pdf') {
      const form = new FormData()
      form.append('file', pdfFile.value)
      form.append('job_description', jobDescription.value)
      data = await streamFetch('/api/analyze/pdf', {
        method: 'POST',
        body: form,
      })
    } else {
      data = await streamFetch('/api/analyze/docs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          docs_url: docsUrl.value,
          job_description: jobDescription.value,
        }),
      })
    }

    result.value = data
  } catch (err) {
    error.value = err.message || 'An unexpected error occurred.'
  } finally {
    loading.value = false
    streamProgress.value = ''
  }
}

// --- Accordion ---
const openQuestions = ref(new Set())
const toggleQuestion = (i) => {
  if (openQuestions.value.has(i)) {
    openQuestions.value.delete(i)
  } else {
    openQuestions.value.add(i)
  }
  // trigger reactivity
  openQuestions.value = new Set(openQuestions.value)
}
</script>

<template>
  <div class="match-layout">
    <!-- LEFT COLUMN: Inputs -->
    <section class="input-column">
      <!-- Tab switcher -->
      <div class="card">
        <h2 class="section-title">Resume</h2>
        <div class="tabs" role="tablist">
          <button
            class="tab-btn"
            :class="{ active: activeTab === 'pdf' }"
            role="tab"
            @click="activeTab = 'pdf'"
          >Upload PDF</button>
          <button
            class="tab-btn"
            :class="{ active: activeTab === 'text' }"
            role="tab"
            @click="activeTab = 'text'"
          >Paste Text</button>
          <button
            class="tab-btn"
            :class="{ active: activeTab === 'docs' }"
            role="tab"
            @click="activeTab = 'docs'"
          >Google Docs</button>
        </div>

        <!-- PDF Upload -->
        <div v-if="activeTab === 'pdf'" class="tab-panel">
          <div
            v-if="!pdfFilename"
            class="drop-zone"
            :class="{ dragging: isDragging }"
            @dragover="handleDragOver"
            @dragleave="handleDragLeave"
            @drop="handleDrop"
            @click="$refs.fileInput.click()"
          >
            <div class="drop-icon">
              <svg width="32" height="32" fill="none" viewBox="0 0 24 24" stroke="#94a3b8" stroke-width="1.5">
                <path stroke-linecap="round" stroke-linejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m6.75 12l-3-3m0 0l-3 3m3-3v6m-1.5-15H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
              </svg>
            </div>
            <p class="drop-text">Drag and drop your PDF here, or <span class="drop-link">browse</span></p>
            <p class="drop-hint">Only .pdf files accepted</p>
            <input
              ref="fileInput"
              type="file"
              accept=".pdf,application/pdf"
              class="file-input-hidden"
              @change="handleFileSelect"
            />
          </div>
          <div v-else class="file-selected">
            <svg width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="#16a34a" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span class="file-name">{{ pdfFilename }}</span>
            <button class="file-clear" @click="clearFile">Remove</button>
          </div>
        </div>

        <!-- Paste Text -->
        <div v-if="activeTab === 'text'" class="tab-panel">
          <textarea
            v-model="resumeText"
            class="textarea"
            placeholder="Paste your resume text here..."
            style="min-height: 200px;"
          ></textarea>
        </div>

        <!-- Google Docs -->
        <div v-if="activeTab === 'docs'" class="tab-panel">
          <input
            v-model="docsUrl"
            type="url"
            class="text-input"
            placeholder="https://docs.google.com/document/d/..."
          />
          <p class="hint-text">Make sure sharing is set to "Anyone with link"</p>
        </div>
      </div>

      <!-- Job Description -->
      <div class="card">
        <label class="label" for="jd">Job Description</label>
        <textarea
          id="jd"
          v-model="jobDescription"
          class="textarea"
          placeholder="Paste the full job description here..."
          style="min-height: 180px;"
        ></textarea>
      </div>

      <!-- Submit -->
      <button
        class="btn-primary"
        :disabled="!canSubmit"
        @click="analyze"
      >
        <template v-if="loading">
          <span class="spinner"></span>
          Analyzing with Claude AI...
        </template>
        <template v-else>
          Analyze Match
        </template>
      </button>

      <!-- Stream progress indicator -->
      <div v-if="loading" class="stream-indicator">
        <span class="dot dot1"></span>
        <span class="dot dot2"></span>
        <span class="dot dot3"></span>
        <span class="stream-label">Streaming response...</span>
      </div>

      <!-- Error -->
      <div v-if="error" class="error-alert">
        <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
        </svg>
        <span>{{ error }}</span>
      </div>
    </section>

    <!-- RIGHT COLUMN: Results -->
    <section v-if="result" class="result-column">

      <!-- Score Card -->
      <div class="card score-card">
        <div class="score-layout">
          <div class="score-circle-wrap">
            <svg class="score-svg" viewBox="0 0 100 100">
              <circle cx="50" cy="50" r="45" fill="none" stroke="#e2e8f0" stroke-width="8"/>
              <circle
                cx="50" cy="50" r="45" fill="none"
                :stroke="scoreColor"
                stroke-width="8"
                stroke-linecap="round"
                stroke-dasharray="283"
                :stroke-dashoffset="283 - (result.overall_score / 100) * 283"
                transform="rotate(-90 50 50)"
                style="transition: stroke-dashoffset 0.8s ease"
              />
            </svg>
            <div class="score-label">
              <span class="score-number" :style="{ color: scoreColor }">{{ result.overall_score }}</span>
              <span class="score-denom">/100</span>
            </div>
          </div>
          <div class="score-meta">
            <span
              class="recommendation-badge"
              :style="{ background: recommendationStyle.bg, color: recommendationStyle.color }"
            >{{ recommendationStyle.label }}</span>
            <p class="summary-text">{{ result.summary }}</p>
          </div>
        </div>
      </div>

      <!-- Matched Skills -->
      <div class="card">
        <h3 class="card-title">Matched Skills</h3>
        <div class="skill-chips">
          <div
            v-for="item in result.matched_skills"
            :key="item.skill"
            class="skill-chip-wrap"
          >
            <span class="skill-chip matched">{{ item.skill }}</span>
            <span v-if="item.evidence" class="skill-evidence">{{ item.evidence }}</span>
          </div>
        </div>
      </div>

      <!-- Missing Skills -->
      <div class="card">
        <h3 class="card-title">Missing Skills</h3>
        <div class="missing-skills-list">
          <div
            v-for="item in result.missing_skills"
            :key="item.skill"
            class="missing-skill-row"
          >
            <div class="missing-skill-header">
              <span class="missing-skill-name">{{ item.skill }}</span>
              <span
                class="importance-badge"
                :style="{ background: importanceBadgeStyle(item.importance).bg, color: importanceBadgeStyle(item.importance).color }"
              >{{ item.importance }}</span>
            </div>
            <p v-if="item.suggestion" class="missing-suggestion">{{ item.suggestion }}</p>
          </div>
        </div>
      </div>

      <!-- Strengths and Concerns -->
      <div class="two-col-cards">
        <div class="card">
          <h3 class="card-title strengths-title">Strengths</h3>
          <ul class="bullet-list strengths-list">
            <li v-for="(s, i) in result.strengths" :key="i" class="bullet-item">
              <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="#16a34a" stroke-width="2.5" class="bullet-icon" style="flex-shrink:0">
                <path stroke-linecap="round" stroke-linejoin="round" d="M4.5 12.75l6 6 9-13.5" />
              </svg>
              <span>{{ s }}</span>
            </li>
          </ul>
        </div>
        <div class="card">
          <h3 class="card-title concerns-title">Concerns</h3>
          <ul class="bullet-list concerns-list">
            <li v-for="(c, i) in result.concerns" :key="i" class="bullet-item">
              <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="#ca8a04" stroke-width="2.5" class="bullet-icon" style="flex-shrink:0">
                <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
              </svg>
              <span>{{ c }}</span>
            </li>
          </ul>
        </div>
      </div>

      <!-- Interview Questions -->
      <div class="card">
        <h3 class="card-title">Interview Questions</h3>
        <div class="accordion">
          <div
            v-for="(q, i) in result.interview_questions"
            :key="i"
            class="accordion-item"
          >
            <button
              class="accordion-trigger"
              @click="toggleQuestion(i)"
              :aria-expanded="openQuestions.has(i)"
            >
              <div class="accordion-trigger-left">
                <span
                  class="category-badge"
                  :style="{ background: categoryBadgeStyle(q.category).bg, color: categoryBadgeStyle(q.category).color }"
                >{{ q.category }}</span>
                <span class="accordion-question">{{ q.question }}</span>
              </div>
              <svg
                class="accordion-chevron"
                :class="{ open: openQuestions.has(i) }"
                width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="#94a3b8" stroke-width="2"
              >
                <path stroke-linecap="round" stroke-linejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
              </svg>
            </button>
            <div v-if="openQuestions.has(i)" class="accordion-body">
              <p class="rationale-text">{{ q.rationale }}</p>
            </div>
          </div>
        </div>
      </div>

    </section>

    <!-- Placeholder when no result yet -->
    <section v-else-if="!loading" class="result-column result-placeholder">
      <div class="placeholder-card">
        <svg width="48" height="48" fill="none" viewBox="0 0 24 24" stroke="#cbd5e1" stroke-width="1.2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M9 12h3.75M9 15h3.75M9 18h3.75m3 .75H18a2.25 2.25 0 002.25-2.25V6.108c0-1.135-.845-2.098-1.976-2.192a48.424 48.424 0 00-1.123-.08m-5.801 0c-.065.21-.1.433-.1.664 0 .414.336.75.75.75h4.5a.75.75 0 00.75-.75 2.25 2.25 0 00-.1-.664m-5.8 0A2.251 2.251 0 0113.5 2.25H15c1.012 0 1.867.668 2.15 1.586m-5.8 0c-.376.023-.75.05-1.124.08C9.095 4.01 8.25 4.973 8.25 6.108V8.25m0 0H4.875c-.621 0-1.125.504-1.125 1.125v11.25c0 .621.504 1.125 1.125 1.125h9.75c.621 0 1.125-.504 1.125-1.125V9.375c0-.621-.504-1.125-1.125-1.125H8.25zM6.75 12h.008v.008H6.75V12zm0 3h.008v.008H6.75V15zm0 3h.008v.008H6.75V18z" />
        </svg>
        <p class="placeholder-text">Your analysis results will appear here after you submit.</p>
      </div>
    </section>
  </div>
</template>

<style scoped>
/* Layout */
.match-layout {
  display: grid;
  grid-template-columns: minmax(340px, 1fr) minmax(340px, 1.4fr);
  gap: 24px;
  align-items: start;
}

@media (max-width: 768px) {
  .match-layout {
    grid-template-columns: 1fr;
  }
}

/* Card */
.card {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.04), 0 1px 2px rgba(0,0,0,0.03);
  margin-bottom: 16px;
}

/* Columns */
.input-column, .result-column {
  display: flex;
  flex-direction: column;
}

/* Titles */
.section-title {
  font-size: 1rem;
  font-weight: 600;
  color: #0f172a;
  margin-bottom: 14px;
}

.card-title {
  font-size: 0.9375rem;
  font-weight: 600;
  color: #0f172a;
  margin-bottom: 14px;
}

.strengths-title { color: #15803d; }
.concerns-title { color: #a16207; }

/* Tabs */
.tabs {
  display: flex;
  gap: 4px;
  background: #f1f5f9;
  border-radius: 8px;
  padding: 4px;
  margin-bottom: 16px;
}

.tab-btn {
  flex: 1;
  padding: 7px 10px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: #64748b;
  font-size: 0.8125rem;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
  white-space: nowrap;
}

.tab-btn.active {
  background: #ffffff;
  color: #0f172a;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}

.tab-btn:hover:not(.active) {
  color: #0f172a;
}

/* Tab panels */
.tab-panel {
  /* nothing special */
}

/* Drop zone */
.drop-zone {
  border: 2px dashed #cbd5e1;
  border-radius: 10px;
  padding: 32px 20px;
  text-align: center;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
  position: relative;
}

.drop-zone:hover, .drop-zone.dragging {
  border-color: #2563eb;
  background: #eff6ff;
}

.drop-icon {
  display: flex;
  justify-content: center;
  margin-bottom: 10px;
}

.drop-text {
  font-size: 0.875rem;
  color: #475569;
}

.drop-link {
  color: #2563eb;
  font-weight: 500;
}

.drop-hint {
  font-size: 0.75rem;
  color: #94a3b8;
  margin-top: 4px;
}

.file-input-hidden {
  position: absolute;
  inset: 0;
  opacity: 0;
  cursor: pointer;
  width: 100%;
  height: 100%;
}

/* File selected */
.file-selected {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
  background: #f0fdf4;
  border: 1px solid #bbf7d0;
  border-radius: 8px;
}

.file-name {
  flex: 1;
  font-size: 0.875rem;
  color: #166534;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-clear {
  background: none;
  border: none;
  color: #64748b;
  font-size: 0.8125rem;
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 4px;
  transition: background 0.1s;
}

.file-clear:hover {
  background: #e2e8f0;
  color: #0f172a;
}

/* Inputs */
.textarea {
  width: 100%;
  padding: 12px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-family: inherit;
  font-size: 0.875rem;
  color: #0f172a;
  resize: vertical;
  transition: border-color 0.15s;
  line-height: 1.6;
}

.textarea:focus {
  outline: none;
  border-color: #2563eb;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
}

.text-input {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-family: inherit;
  font-size: 0.875rem;
  color: #0f172a;
  transition: border-color 0.15s;
}

.text-input:focus {
  outline: none;
  border-color: #2563eb;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
}

.hint-text {
  font-size: 0.75rem;
  color: #94a3b8;
  margin-top: 6px;
}

/* Label */
.label {
  display: block;
  font-size: 0.875rem;
  font-weight: 600;
  color: #374151;
  margin-bottom: 8px;
}

/* Button */
.btn-primary {
  width: 100%;
  padding: 13px 20px;
  background: #2563eb;
  color: #ffffff;
  border: none;
  border-radius: 8px;
  font-family: inherit;
  font-size: 0.9375rem;
  font-weight: 600;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  transition: background 0.15s, opacity 0.15s;
  margin-bottom: 12px;
}

.btn-primary:hover:not(:disabled) {
  background: #1d4ed8;
}

.btn-primary:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

/* Spinner */
.spinner {
  width: 18px;
  height: 18px;
  border: 2px solid rgba(255,255,255,0.35);
  border-top-color: #ffffff;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
  flex-shrink: 0;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Stream indicator */
.stream-indicator {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 14px;
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  border-radius: 8px;
  margin-bottom: 12px;
}

.dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #2563eb;
  animation: bounce 1.2s ease-in-out infinite;
}

.dot2 { animation-delay: 0.2s; }
.dot3 { animation-delay: 0.4s; }

@keyframes bounce {
  0%, 80%, 100% { transform: scale(0.7); opacity: 0.5; }
  40% { transform: scale(1); opacity: 1; }
}

.stream-label {
  font-size: 0.8125rem;
  color: #1d4ed8;
  font-weight: 500;
}

/* Error */
.error-alert {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 14px 16px;
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 8px;
  color: #b91c1c;
  font-size: 0.875rem;
  line-height: 1.5;
}

/* Score card */
.score-card {
  margin-bottom: 16px;
}

.score-layout {
  display: flex;
  align-items: flex-start;
  gap: 20px;
}

.score-circle-wrap {
  position: relative;
  width: 100px;
  height: 100px;
  flex-shrink: 0;
}

.score-svg {
  width: 100px;
  height: 100px;
}

.score-label {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.score-number {
  font-size: 1.625rem;
  font-weight: 700;
  line-height: 1;
}

.score-denom {
  font-size: 0.6875rem;
  color: #94a3b8;
}

.score-meta {
  flex: 1;
}

.recommendation-badge {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 20px;
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: capitalize;
  margin-bottom: 10px;
}

.summary-text {
  font-size: 0.875rem;
  color: #475569;
  line-height: 1.6;
}

/* Skills */
.skill-chips {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.skill-chip-wrap {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.skill-chip {
  display: inline-block;
  padding: 4px 10px;
  border-radius: 20px;
  font-size: 0.8125rem;
  font-weight: 500;
}

.skill-chip.matched {
  background: #dcfce7;
  color: #15803d;
}

.skill-evidence {
  font-size: 0.75rem;
  color: #94a3b8;
  padding-left: 2px;
}

/* Missing skills */
.missing-skills-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.missing-skill-row {
  padding: 12px;
  background: #fafafa;
  border: 1px solid #f1f5f9;
  border-radius: 8px;
}

.missing-skill-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.missing-skill-name {
  font-size: 0.875rem;
  font-weight: 600;
  color: #0f172a;
}

.importance-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 0.6875rem;
  font-weight: 600;
  text-transform: capitalize;
}

.missing-suggestion {
  font-size: 0.8125rem;
  color: #64748b;
  line-height: 1.5;
}

/* Two col */
.two-col-cards {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 0;
}

@media (max-width: 600px) {
  .two-col-cards {
    grid-template-columns: 1fr;
  }
}

/* Bullet lists */
.bullet-list {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.bullet-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: 0.875rem;
  color: #374151;
  line-height: 1.5;
}

.bullet-icon {
  margin-top: 2px;
}

/* Accordion */
.accordion {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.accordion-item {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  overflow: hidden;
}

.accordion-trigger {
  width: 100%;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 16px;
  background: #fafafa;
  border: none;
  cursor: pointer;
  text-align: left;
  font-family: inherit;
  transition: background 0.1s;
}

.accordion-trigger:hover {
  background: #f1f5f9;
}

.accordion-trigger-left {
  display: flex;
  flex-direction: column;
  gap: 6px;
  flex: 1;
}

.accordion-question {
  font-size: 0.875rem;
  font-weight: 500;
  color: #0f172a;
  line-height: 1.5;
}

.category-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 0.6875rem;
  font-weight: 600;
  text-transform: capitalize;
  align-self: flex-start;
}

.accordion-chevron {
  flex-shrink: 0;
  margin-top: 2px;
  transition: transform 0.2s;
}

.accordion-chevron.open {
  transform: rotate(180deg);
}

.accordion-body {
  padding: 12px 16px;
  border-top: 1px solid #e2e8f0;
  background: #ffffff;
}

.rationale-text {
  font-size: 0.8125rem;
  color: #64748b;
  line-height: 1.6;
}

/* Placeholder */
.result-placeholder {
  /* no result yet */
}

.placeholder-card {
  background: #ffffff;
  border: 1px dashed #e2e8f0;
  border-radius: 12px;
  padding: 48px 20px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 14px;
  text-align: center;
}

.placeholder-text {
  font-size: 0.875rem;
  color: #94a3b8;
  max-width: 260px;
}
</style>
