<script setup>
import MatchView from './views/MatchView.vue'
</script>

<template>
  <div id="app">
    <header class="app-header">
      <div class="header-inner">
        <h1 class="app-title">Job-Resume Matcher</h1>
        <p class="app-subtitle">AI-powered resume analysis via Claude</p>
      </div>
    </header>
    <main class="app-main">
      <MatchView />
    </main>
  </div>
</template>

<style>
*, *::before, *::after {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

html {
  font-size: 16px;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

body {
  font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background-color: #f8fafc;
  color: #0f172a;
  line-height: 1.5;
  min-height: 100vh;
}

#app {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.app-header {
  background: #ffffff;
  border-bottom: 1px solid #e2e8f0;
  padding: 0 24px;
}

.header-inner {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px 0;
}

.app-title {
  font-size: 1.5rem;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: -0.02em;
}

.app-subtitle {
  font-size: 0.875rem;
  color: #64748b;
  margin-top: 2px;
}

.app-main {
  flex: 1;
  max-width: 1200px;
  margin: 0 auto;
  width: 100%;
  padding: 32px 24px;
}

@media (max-width: 768px) {
  .app-main {
    padding: 20px 16px;
  }
}
</style>
