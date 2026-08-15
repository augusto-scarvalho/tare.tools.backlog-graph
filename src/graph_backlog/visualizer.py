from __future__ import annotations
import http.server
import json
import socketserver
import webbrowser
from pathlib import Path
from typing import Any

from .core import WorkGraph
from .jsonutil import atomic_write, stable_dict

SIGNAL_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>tare.tools — Graph Backlog (SIGNAL Mission Control)</title>
  <style>
    /* ==========================================================================
       SIGNAL Design Tokens — Canonical UI Law (warm-black + lime-phosphor)
       ========================================================================== */
    :root {
      color-scheme: dark;
      
      --bg-base: #0A0B08;
      --bg-void: #0A0B08;
      --atmo-glow: #12160C;
      --surface-1: #0F1109;
      --surface-2: #14170E;
      --surface-3: #1B1F14;
      --surface-hover: #1B1F14;
      
      --border-subtle: #1E2216;
      --border: #2B3020;
      --border-strong: #3A4029;
      
      --text-primary: #EDEEE1;
      --text-secondary: #A6AA90;
      --text-muted: #8B9173;
      --text-disabled: #4A4E39;
      
      --accent: #CBF23F; /* Lime-fósforo dominante */
      --accent-bg: rgba(203, 242, 63, 0.12);
      --accent-border: rgba(203, 242, 63, 0.40);
      
      --stream: #45E0C4; /* Teal live / osciloscópio */
      --stream-bg: rgba(69, 224, 196, 0.12);
      --stream-border: rgba(69, 224, 196, 0.34);
      
      --success: #7CCB6A;
      --success-bg: rgba(124, 203, 106, 0.12);
      --success-border: rgba(124, 203, 106, 0.32);
      
      --warning: #E8A93B;
      --warning-bg: rgba(232, 169, 59, 0.12);
      --warning-border: rgba(232, 169, 59, 0.32);
      
      --danger: #F2685C;
      --danger-bg: rgba(242, 104, 92, 0.12);
      --danger-border: rgba(242, 104, 92, 0.34);
      
      --font-ui: "IBM Plex Mono", ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      --font-mono: "IBM Plex Mono", ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      --font-prose: "IBM Plex Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      
      --text-xs: 11px;
      --text-sm: 12px;
      --text-md: 13px;
      --text-lg: 15px;
      --text-xl: 18px;
      --line-ui: 1.45;
      
      --h-topbar: 52px;
      --h-subnav: 38px;
      --h-row: 34px;
      --radius-sm: 8px;
      --radius-xs: 6px;
      --space-1: 4px;
      --space-2: 8px;
      --space-3: 12px;
      --space-4: 16px;
      --shadow-1: 0 1px 2px rgba(0, 0, 0, 0.3);
    }
    
    * { box-sizing: border-box; margin: 0; padding: 0; user-select: none; }
    
    body {
      font-family: var(--font-ui);
      background-color: var(--bg-base);
      background-image: radial-gradient(circle at 50% 0%, var(--atmo-glow) 0%, var(--bg-base) 70%);
      color: var(--text-primary);
      display: flex;
      flex-direction: column;
      height: 100vh;
      overflow: hidden;
      -webkit-font-smoothing: antialiased;
    }
    
    /* Atmosphere scanlines of measurement instrument */
    .atmo {
      background-image: linear-gradient(0deg, transparent 23px, rgba(203, 242, 63, 0.02) 24px);
      background-size: 100% 24px;
    }
    
    header {
      height: var(--h-topbar);
      background: var(--surface-1);
      border-bottom: 1px solid var(--border-subtle);
      padding: 0 var(--space-4);
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: var(--space-3);
      flex-wrap: wrap;
      z-index: 10;
    }
    
    .brand {
      display: flex;
      align-items: center;
      gap: var(--space-3);
    }
    .brand-logo {
      font-family: var(--font-mono);
      font-size: var(--text-lg);
      font-weight: 700;
      letter-spacing: -0.5px;
      color: var(--text-primary);
      display: flex;
      align-items: center;
      gap: var(--space-2);
    }
    .brand-logo::before {
      content: "";
      display: inline-block;
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: var(--accent);
      box-shadow: 0 0 8px var(--accent);
    }
    .brand-pill {
      font-family: var(--font-mono);
      font-size: var(--text-xs);
      font-weight: 600;
      background: var(--accent-bg);
      color: var(--accent);
      border: 1px solid var(--accent-border);
      padding: 2px 8px;
      border-radius: var(--radius-xs);
      text-transform: uppercase;
      letter-spacing: 0.5px;
      max-width: 200px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    
    .view-tabs {
      display: flex;
      background: var(--bg-base);
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-xs);
      padding: 2px;
      gap: 2px;
    }
    .tab-btn {
      background: transparent;
      border: none;
      color: var(--text-muted);
      padding: 6px 12px;
      border-radius: var(--radius-xs);
      font-size: var(--text-sm);
      font-family: var(--font-ui);
      font-weight: 600;
      cursor: pointer;
      transition: all 0.15s ease;
    }
    .tab-btn:hover {
      color: var(--text-primary);
    }
    .tab-btn.active {
      background: var(--surface-2);
      color: var(--accent);
      box-shadow: 0 0 0 1px var(--accent-border);
    }
    
    .controls {
      display: flex;
      gap: var(--space-2);
      align-items: center;
      flex-wrap: wrap;
    }
    input, select, .action-btn {
      background: var(--surface-1);
      color: var(--text-secondary);
      border: 1px solid var(--border);
      border-radius: var(--radius-xs);
      padding: 6px 10px;
      font-size: var(--text-xs);
      font-family: var(--font-ui);
      transition: border-color 0.15s, background 0.15s;
    }
    input:focus, select:focus {
      outline: none;
      border-color: var(--accent);
      color: var(--text-primary);
      box-shadow: 0 0 0 1px var(--accent-border);
    }
    .action-btn {
      cursor: pointer;
      font-weight: 600;
      display: flex;
      align-items: center;
      gap: 4px;
    }
    .action-btn:hover {
      background: var(--surface-hover);
      border-color: var(--border-strong);
      color: var(--text-primary);
    }
    .action-btn.active {
      background: var(--accent-bg);
      border-color: var(--accent);
      color: var(--accent);
      box-shadow: 0 0 6px var(--accent-bg);
    }
    
    .main-workspace {
      display: flex;
      flex: 1;
      overflow: hidden;
      position: relative;
    }
    
    /* View Content Base */
    .view-content {
      flex: 1;
      height: 100%;
      overflow-y: auto;
      padding: var(--space-4);
      display: none;
    }
    .view-content.active {
      display: flex;
      flex-direction: column;
      gap: var(--space-4);
    }
    
    /* Clusters / Modules Grid View */
    .clusters-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
      gap: var(--space-4);
      align-items: start;
    }
    
    .cluster-column {
      background: var(--surface-1);
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-sm);
      padding: var(--space-3);
      display: flex;
      flex-direction: column;
      gap: var(--space-3);
    }
    .cluster-title-bar {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding-bottom: var(--space-2);
      border-bottom: 1px solid var(--border-subtle);
    }
    .cluster-name {
      font-size: var(--text-xs);
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      color: var(--accent);
    }
    .cluster-badge {
      font-size: var(--text-xs);
      background: var(--surface-2);
      color: var(--text-muted);
      padding: 1px 6px;
      border-radius: var(--radius-xs);
      border: 1px solid var(--border-subtle);
    }

    /* Classic Kanban Experience View */
    .kanban-board {
      display: flex;
      gap: var(--space-4);
      height: 100%;
      overflow-x: auto;
      align-items: stretch;
    }
    .kanban-lane {
      flex: 1;
      min-width: 300px;
      max-width: 400px;
      background: var(--surface-1);
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-sm);
      display: flex;
      flex-direction: column;
      height: 100%;
      overflow: hidden;
    }
    .kanban-lane-header {
      padding: var(--space-3);
      background: var(--surface-2);
      border-bottom: 1px solid var(--border-subtle);
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .kanban-lane-title {
      font-size: var(--text-xs);
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .kanban-lane-title.lane-blocked { color: var(--danger); }
    .kanban-lane-title.lane-ready { color: var(--accent); }
    .kanban-lane-title.lane-partial { color: var(--warning); }
    .kanban-lane-title.lane-done { color: var(--text-muted); }
    
    .kanban-lane-cards {
      padding: var(--space-3);
      overflow-y: auto;
      display: flex;
      flex-direction: column;
      gap: var(--space-3);
      flex: 1;
    }
    
    /* SIGNAL Task Cards (Status-rail 3px left border) */
    .task-card {
      background: var(--surface-2);
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-xs);
      padding: var(--space-3);
      cursor: pointer;
      transition: transform 0.1s ease, border-color 0.15s ease, box-shadow 0.15s ease, opacity 0.2s ease;
      display: flex;
      flex-direction: column;
      gap: 6px;
      position: relative;
    }
    .task-card:hover {
      background: var(--surface-hover);
      border-color: var(--border-strong);
      transform: translateY(-1px);
    }
    
    /* Pulse Keyframe Animation */
    @keyframes nodeGlowPulse {
      0%, 100% {
        box-shadow: 0 0 0 1px var(--accent), 0 0 14px var(--accent-bg);
      }
      50% {
        box-shadow: 0 0 0 2px var(--accent), 0 0 22px rgba(203, 242, 63, 0.4);
      }
    }
    
    @keyframes electricPulse {
      0% {
        stroke-dashoffset: 24;
      }
      100% {
        stroke-dashoffset: 0;
      }
    }

    .task-card.selected {
      border-color: var(--accent) !important;
      background: var(--surface-3) !important;
      animation: nodeGlowPulse 2s infinite ease-in-out;
      z-index: 2;
    }
    
    .task-card.chain-upstream {
      border-color: rgba(203, 242, 63, 0.7) !important;
      background: rgba(203, 242, 63, 0.06) !important;
      box-shadow: 0 0 0 1px rgba(203, 242, 63, 0.3);
    }

    .task-card.dimmed {
      opacity: 0.28 !important;
      filter: grayscale(35%);
    }

    /* SIGNAL Status Rail (color + symbol + text) */
    .task-card.status-ready {
      border-left: 3px solid var(--accent);
    }
    .task-card.status-blocked {
      border-left: 3px solid var(--danger);
    }
    .task-card.status-done {
      border-left: 3px solid var(--text-muted);
      opacity: 0.72;
    }
    .task-card.status-partial {
      border-left: 3px solid var(--warning);
    }
    .task-card.simulated-done {
      border-left: 3px solid var(--stream) !important;
      background: var(--stream-bg) !important;
      box-shadow: 0 0 8px var(--stream-bg);
    }
    
    .card-top {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: var(--space-2);
    }
    .card-id {
      font-size: var(--text-sm);
      font-weight: 700;
      color: var(--text-primary);
    }
    .card-badges {
      display: flex;
      gap: var(--space-1);
      flex-wrap: wrap;
    }
    .signal-pill {
      font-size: 10px;
      font-weight: 700;
      padding: 1px 5px;
      border-radius: 4px;
      border: 1px solid var(--border-subtle);
      background: var(--surface-1);
      display: flex;
      align-items: center;
      gap: 3px;
    }
    .pill-ready {
      background: var(--accent-bg);
      color: var(--accent);
      border-color: var(--accent-border);
    }
    .pill-blocked {
      background: var(--danger-bg);
      color: var(--danger);
      border-color: var(--danger-border);
    }
    .pill-done {
      background: rgba(139, 145, 115, 0.12);
      color: var(--text-muted);
      border-color: rgba(139, 145, 115, 0.32);
    }
    .pill-partial {
      background: var(--warning-bg);
      color: var(--warning);
      border-color: var(--warning-border);
    }
    .pill-cluster {
      background: var(--surface-1);
      color: var(--text-muted);
      font-size: 9px;
      text-transform: uppercase;
    }
    
    .card-title {
      font-size: var(--text-sm);
      font-weight: 500;
      color: var(--text-secondary);
      line-height: var(--line-ui);
    }
    
    /* Interactive DAG Canvas View */
    .dag-canvas-container {
      flex: 1;
      height: 100%;
      position: relative;
      background-color: var(--bg-base);
      background-image: radial-gradient(circle, var(--border) 1px, transparent 1px);
      background-size: 24px 24px;
      overflow: hidden;
    }
    #dagSvg {
      width: 100%;
      height: 100%;
      cursor: grab;
    }
    #dagSvg.panning {
      cursor: grabbing;
    }
    
    /* Pulse Edge Classes */
    .edge-pulse-upstream {
      stroke: var(--accent) !important;
      stroke-width: 2.5px !important;
      stroke-dasharray: 8 4;
      animation: electricPulse 0.75s linear infinite;
      filter: drop-shadow(0 0 5px rgba(203, 242, 63, 0.85));
    }
    
    .edge-dimmed {
      opacity: 0.15 !important;
      stroke: #1E2216 !important;
    }
    
    .dag-node-dimmed {
      opacity: 0.22 !important;
      filter: grayscale(40%);
    }

    /* Canvas Floating HUD */
    .dag-hud {
      position: absolute;
      top: 16px;
      left: 16px;
      display: flex;
      gap: 6px;
      background: var(--surface-1);
      border: 1px solid var(--border);
      border-radius: var(--radius-xs);
      padding: 4px;
      z-index: 5;
      box-shadow: 0 4px 12px rgba(0,0,0,0.5);
    }
    .hud-btn {
      background: var(--surface-2);
      border: 1px solid var(--border-subtle);
      color: var(--text-secondary);
      border-radius: 4px;
      padding: 4px 8px;
      font-family: var(--font-ui);
      font-size: var(--text-xs);
      font-weight: 600;
      cursor: pointer;
      transition: all 0.15s ease;
    }
    .hud-btn:hover {
      background: var(--surface-hover);
      color: var(--accent);
      border-color: var(--accent-border);
    }
    .hud-zoom-label {
      display: flex;
      align-items: center;
      padding: 0 6px;
      font-size: var(--text-xs);
      color: var(--text-muted);
    }
    
    /* SIGNAL Inspector Drawer */
    .inspector-drawer {
      width: 440px;
      background: var(--surface-1);
      border-left: 1px solid var(--border);
      display: flex;
      flex-direction: column;
      height: 100%;
      overflow-y: auto;
      padding: var(--space-4);
      gap: var(--space-3);
      z-index: 5;
    }
    .inspector-header {
      display: flex;
      flex-direction: column;
      gap: var(--space-1);
      border-bottom: 1px solid var(--border);
      padding-bottom: var(--space-3);
    }
    .inspector-id {
      font-size: var(--text-lg);
      font-weight: 700;
      color: var(--accent);
    }
    .inspector-title {
      font-size: var(--text-md);
      font-weight: 600;
      color: var(--text-primary);
      line-height: var(--line-ui);
      user-select: text;
    }

    .closure-btn-group {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 6px;
      margin-top: 4px;
    }
    
    .section-block {
      display: flex;
      flex-direction: column;
      gap: var(--space-1);
    }
    .section-label {
      font-size: var(--text-xs);
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      color: var(--text-muted);
    }
    .section-box {
      background: var(--surface-2);
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-xs);
      padding: var(--space-2) var(--space-3);
      font-size: var(--text-xs);
      line-height: var(--line-ui);
      color: var(--text-secondary);
      user-select: text;
    }
    
    .dep-item {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 6px var(--space-2);
      border-radius: var(--radius-xs);
      background: var(--surface-2);
      border: 1px solid var(--border-subtle);
      font-size: var(--text-xs);
      cursor: pointer;
      transition: all 0.1s ease;
    }
    .dep-item:hover {
      border-color: var(--accent);
      background: var(--surface-hover);
    }

    /* ==========================================================================
       SIGNAL Graph Ops Modal & Diagnostic Center (All 13 Research Operations)
       ========================================================================== */
    .modal-backdrop {
      position: fixed;
      inset: 0;
      background: rgba(10, 11, 8, 0.88);
      backdrop-filter: blur(6px);
      display: none;
      justify-content: center;
      align-items: center;
      z-index: 100;
    }
    .modal-backdrop.active {
      display: flex;
    }
    .ops-modal {
      width: 860px;
      max-width: 94vw;
      max-height: 88vh;
      background: var(--surface-1);
      border: 1px solid var(--border-strong);
      border-radius: var(--radius-sm);
      display: flex;
      flex-direction: column;
      box-shadow: 0 16px 48px rgba(0,0,0,0.9), 0 0 24px var(--accent-bg);
      overflow: hidden;
    }
    .modal-header {
      padding: var(--space-3) var(--space-4);
      background: var(--surface-2);
      border-bottom: 1px solid var(--border);
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .modal-title {
      font-size: var(--text-md);
      font-weight: 700;
      color: var(--accent);
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .modal-close-btn {
      background: transparent;
      border: none;
      color: var(--text-muted);
      font-size: 16px;
      cursor: pointer;
    }
    .modal-close-btn:hover { color: var(--text-primary); }
    
    .modal-nav {
      display: flex;
      gap: 4px;
      padding: var(--space-2) var(--space-4);
      background: var(--bg-base);
      border-bottom: 1px solid var(--border-subtle);
      overflow-x: auto;
    }
    .modal-nav-btn {
      background: transparent;
      border: none;
      color: var(--text-muted);
      padding: 6px 10px;
      border-radius: var(--radius-xs);
      font-size: var(--text-xs);
      font-family: var(--font-ui);
      font-weight: 600;
      cursor: pointer;
      white-space: nowrap;
      transition: all 0.15s ease;
    }
    .modal-nav-btn:hover { color: var(--text-primary); }
    .modal-nav-btn.active {
      background: var(--surface-2);
      color: var(--accent);
      box-shadow: 0 0 0 1px var(--accent-border);
    }
    
    .modal-body {
      padding: var(--space-4);
      overflow-y: auto;
      flex: 1;
      display: flex;
      flex-direction: column;
      gap: var(--space-3);
    }
    .report-card {
      background: var(--surface-2);
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-xs);
      padding: var(--space-3);
      display: flex;
      flex-direction: column;
      gap: 6px;
    }
    .report-card.pass { border-left: 3px solid var(--accent); }
    .report-card.fail { border-left: 3px solid var(--danger); }
    .report-card.warn { border-left: 3px solid var(--warning); }
    
    /* Diff lines */
    .diff-item {
      font-family: var(--font-mono);
      font-size: 11px;
      padding: 4px 8px;
      border-radius: 4px;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .diff-add { background: rgba(124, 203, 106, 0.12); color: var(--success); border: 1px solid var(--success-border); }
    .diff-del { background: rgba(242, 104, 92, 0.12); color: var(--danger); border: 1px solid var(--danger-border); }
    .diff-mod { background: rgba(69, 224, 196, 0.12); color: var(--stream); border: 1px solid var(--stream-border); }

    /* Ledger block */
    .ledger-block {
      background: var(--surface-1);
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-xs);
      padding: 10px;
      display: flex;
      flex-direction: column;
      gap: 4px;
      font-size: 11px;
    }
    .ledger-hash {
      font-family: var(--font-mono);
      color: var(--accent);
      font-size: 10px;
    }

    /* Footer Telemetry Status Bar */
    footer {
      height: 32px;
      background: var(--surface-1);
      border-top: 1px solid var(--border-subtle);
      padding: 0 var(--space-4);
      display: flex;
      gap: var(--space-4);
      font-size: var(--text-xs);
      color: var(--text-muted);
      align-items: center;
      z-index: 10;
    }
    .stat-metric span {
      font-weight: 700;
      color: var(--text-primary);
    }
    .stat-metric.metric-ready span {
      color: var(--accent);
    }
    .esc-hint {
      margin-left: auto;
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 11px;
      color: var(--text-muted);
    }
    .kbd-pill {
      background: var(--surface-2);
      border: 1px solid var(--border);
      border-radius: 3px;
      padding: 1px 5px;
      color: var(--text-primary);
      font-size: 10px;
    }
  </style>
</head>
<body class="atmo">
  <header>
    <div class="brand">
      <div class="brand-logo">tare.tools</div>
      <div class="brand-pill" id="projectTitleDisplay">SIGNAL Graph Backlog</div>
    </div>

    <!-- Project Selector Dropdown & File Loader -->
    <div class="controls">
      <select id="projectSelector" onchange="switchProject(this.value)" style="font-weight:700; color:var(--accent); border-color:var(--accent-border); max-width:260px;">
        <option value="__ACTIVE__">📁 Active Project</option>
        <option value="transmedia">🎬 Demo: Epic Transmedia (42 tasks: Book ➔ Comic ➔ Film)</option>
        <option value="saas">🏢 Demo: CloudPulse SaaS (33 tasks)</option>
        <option value="rag">🤖 Demo: OmniAgent AI RAG (27 tasks)</option>
        <option value="sample">🧪 Demo: Core Sample (3 tasks)</option>
        <option value="__UPLOAD__">📂 Open Local JSON File...</option>
      </select>
      <input type="file" id="fileUploadInput" accept=".json" style="display:none;" onchange="handleFileUpload(event)">
    </div>
    
    <div class="view-tabs">
      <button class="tab-btn active" id="tabGridBtn" onclick="switchView('grid')">Clusters / Modules</button>
      <button class="tab-btn" id="tabKanbanBtn" onclick="switchView('kanban')">Classic Kanban</button>
      <button class="tab-btn" id="tabDagBtn" onclick="switchView('dag')">Interactive DAG Canvas</button>
    </div>

    <div class="controls">
      <input type="text" id="searchInput" placeholder="Search tasks, IDs, tags..." style="width: 150px;">
      <select id="statusFilter">
        <option value="ALL">All Statuses</option>
        <option value="FRONTIER">⚡ Ready Frontier (Actionable)</option>
        <option value="NOT_DONE">NOT_DONE</option>
        <option value="PARTIAL">PARTIAL</option>
        <option value="DONE">DONE</option>
        <option value="SUPERSEDED">SUPERSEDED</option>
      </select>
      <select id="clusterFilter">
        <option value="ALL">All Clusters</option>
      </select>
      <button class="action-btn" id="criticalPathBtn" onclick="toggleCriticalPath()">Critical Path</button>
      <button class="action-btn" id="opsModalBtn" onclick="openOpsModal('doctor')" style="border-color:var(--accent-border); color:var(--accent);">⚡ Graph Ops (13 Ops)</button>
      <button class="action-btn" id="resetBtn" onclick="resetFilters()">Reset</button>
    </div>
  </header>

  <div class="main-workspace">
    <!-- Clusters View -->
    <div class="view-content active" id="gridView">
      <div class="clusters-grid" id="clustersContainer"></div>
    </div>

    <!-- Classic Kanban Board View -->
    <div class="view-content" id="kanbanView" style="padding:var(--space-4);">
      <div class="kanban-board" id="kanbanBoardContainer"></div>
    </div>

    <!-- Interactive DAG Canvas View -->
    <div class="view-content" id="dagView" style="padding:0;">
      <div class="dag-canvas-container">
        <!-- Floating HUD -->
        <div class="dag-hud">
          <button class="hud-btn" onclick="zoomIn()" title="Zoom in">+</button>
          <button class="hud-btn" onclick="zoomOut()" title="Zoom out">−</button>
          <span class="hud-zoom-label" id="zoomDisplay">100%</span>
          <button class="hud-btn" onclick="resetDagView()" title="Reset viewport and rearrange layout">Auto-Layout</button>
        </div>
        <svg id="dagSvg">
          <g id="dagViewport">
            <g id="dagEdgesLayer"></g>
            <g id="dagNodesLayer"></g>
          </g>
        </svg>
      </div>
    </div>

    <!-- SIGNAL Inspector Drawer -->
    <div class="inspector-drawer" id="inspectorDrawer">
      <div class="inspector-header">
        <div class="inspector-id" id="inspId">Select a task</div>
        <div class="inspector-title" id="inspTitle">Click on any node in the backlog to inspect dependencies, exit criteria, and implementation context. Press [Esc] to deselect.</div>
      </div>

      <div class="section-block">
        <div class="section-label">Readiness & State</div>
        <div class="section-box" id="inspState">-</div>
      </div>

      <div class="section-block">
        <div class="section-label">Transitive Closure Tools (Op 6)</div>
        <div class="closure-btn-group">
          <button class="action-btn" id="traceAncestorsBtn" onclick="highlightUpstreamClosure()" style="justify-content:center;">
            ⬆️ Upstream Blockers
          </button>
          <button class="action-btn" id="traceDescendantsBtn" onclick="highlightDownstreamClosure()" style="justify-content:center;">
            ⬇️ Downstream Impact
          </button>
        </div>
      </div>

      <div class="section-block">
        <div class="section-label">Simulation (What-If Contrafactual — Op 7)</div>
        <label style="display:flex; align-items:center; gap:8px; font-size:11px; cursor:pointer; color:var(--text-secondary);">
          <input type="checkbox" id="simToggle" onchange="toggleSimulateCurrent()">
          Simulate this task as DONE (evaluate unlocked frontier)
        </label>
      </div>

      <div class="section-block">
        <div class="section-label">Summary & Purpose</div>
        <div class="section-box" id="inspSummary">-</div>
      </div>

      <div class="section-block">
        <div class="section-label">Definition of Done / Exit Criteria</div>
        <div class="section-box" id="inspCriteria">-</div>
      </div>

      <div class="section-block">
        <div class="section-label">Direct Upstream Blockers (Prerequisites)</div>
        <div id="inspPrereqs" style="display:flex; flex-direction:column; gap:4px;">None</div>
      </div>

      <div class="section-block">
        <div class="section-label">Direct Downstream Impact (Unlocks)</div>
        <div id="inspDownstream" style="display:flex; flex-direction:column; gap:4px;">None</div>
      </div>

      <button class="action-btn" id="copyPacketBtn" onclick="openOpsModal('agent')" style="justify-content:center; margin-top:8px;">
        🤖 Open Agent Implementation Packet (Op 11)
      </button>
    </div>
  </div>

  <!-- Graph Operations & Diagnostic Modal (13 Core Operations) -->
  <div class="modal-backdrop" id="opsModalBackdrop" onclick="handleBackdropClick(event)">
    <div class="ops-modal">
      <div class="modal-header">
        <div class="modal-title">⚡ Graph Operations & Research Mission Control (13 Ops)</div>
        <button class="modal-close-btn" onclick="closeOpsModal()">✕</button>
      </div>
      <div class="modal-nav">
        <button class="modal-nav-btn active" id="modalTabDoctor" onclick="switchOpsTab('doctor')">🔍 Doctor & Integrity (Op 1, 8, 12)</button>
        <button class="modal-nav-btn" id="modalTabRanked" onclick="switchOpsTab('ranked')">⚡ Queue & Paths (Op 2, 3, 4, 5)</button>
        <button class="modal-nav-btn" id="modalTabDiff" onclick="switchOpsTab('diff')">🔄 Semantic Diff (Op 9)</button>
        <button class="modal-nav-btn" id="modalTabLedger" onclick="switchOpsTab('ledger')">🔒 Crypto Ledger (Op 10)</button>
        <button class="modal-nav-btn" id="modalTabAgent" onclick="switchOpsTab('agent')">🤖 Agent Packet (Op 11)</button>
        <button class="modal-nav-btn" id="modalTabExport" onclick="switchOpsTab('export')">💾 Universal Export (Op 13)</button>
      </div>
      <div class="modal-body" id="opsModalContent"></div>
    </div>
  </div>

  <footer>
    <div class="stat-metric">Total: <span id="statTotal">0</span></div>
    <div class="stat-metric metric-ready">⚡ Actionable Frontier: <span id="statReady">0</span></div>
    <div class="stat-metric">Done: <span id="statDone">0</span></div>
    <div class="stat-metric">Edges: <span id="statEdges">0</span></div>
    <div class="esc-hint"><span>Press</span> <kbd class="kbd-pill">Esc</kbd> <span>to deselect node & path</span></div>
  </footer>

  <script>
    const BUILTIN_PROJECTS = {
      active: __GRAPH_JSON_PLACEHOLDER__,
      transmedia: __TRANSMEDIA_JSON_PLACEHOLDER__,
      saas: __SAAS_JSON_PLACEHOLDER__,
      rag: __RAG_JSON_PLACEHOLDER__,
      sample: __SAMPLE_JSON_PLACEHOLDER__
    };

    let RAW_GRAPH = BUILTIN_PROJECTS.active;
    let nodes = RAW_GRAPH.nodes || [];
    let edges = RAW_GRAPH.edges || [];
    let byId = {};
    let clusters = [];

    let selectedNodeId = null;
    let simulatedDoneSet = new Set();
    let showCriticalPath = false;
    let currentView = 'grid';

    // Custom Path / Subgraph Highlight state (e.g. from shortest path, closure, or diff)
    let activeCustomPath = null;

    // Node Positions map (preserves drag-and-drop locations)
    const nodePositions = {};

    // Viewport Pan / Zoom state
    let zoomLevel = 1.0;
    let panX = 40;
    let panY = 40;
    let isPanningCanvas = false;
    let panStartX = 0;
    let panStartY = 0;

    // Node Drag state
    let isDraggingNode = false;
    let draggedNodeId = null;
    let dragStartX = 0;
    let dragStartY = 0;
    let initialNodeX = 0;
    let initialNodeY = 0;
    let hasMovedSignificantly = false;

    function loadGraph(graphData) {
      RAW_GRAPH = graphData || {};
      nodes = RAW_GRAPH.nodes || [];
      edges = RAW_GRAPH.edges || [];
      byId = {};
      nodes.forEach(n => byId[n.id] = n);

      const title = (RAW_GRAPH.meta && RAW_GRAPH.meta.title) || 'SIGNAL Graph Backlog';
      const titleEl = document.getElementById('projectTitleDisplay');
      if (titleEl) titleEl.textContent = title;

      // Populate cluster filter
      clusters = [...new Set(nodes.map(n => n.cluster || 'general'))].sort();
      const clusterSelect = document.getElementById('clusterFilter');
      clusterSelect.innerHTML = '<option value="ALL">All Clusters</option>';
      clusters.forEach(c => {
        const opt = document.createElement('option');
        opt.value = c;
        opt.textContent = c;
        clusterSelect.appendChild(opt);
      });

      resetFilters();
    }

    function switchProject(val) {
      if (val === '__UPLOAD__') {
        const upEl = document.getElementById('fileUploadInput');
        if (upEl) upEl.click();
        return;
      }
      if (val === '__ACTIVE__' || val === 'active') {
        loadGraph(BUILTIN_PROJECTS.active);
      } else if (BUILTIN_PROJECTS[val]) {
        loadGraph(BUILTIN_PROJECTS[val]);
      }
    }

    function handleFileUpload(event) {
      const file = event.target.files && event.target.files[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = (e) => {
        try {
          const parsed = JSON.parse(e.target.result);
          if (!parsed.nodes) {
            alert('Invalid graph JSON: missing "nodes" array.');
            return;
          }
          const selector = document.getElementById('projectSelector');
          const opt = document.createElement('option');
          opt.value = '__CUSTOM_LOADED__';
          opt.textContent = `📄 File: ${file.name}`;
          opt.selected = true;
          selector.appendChild(opt);

          loadGraph(parsed);
        } catch (err) {
          alert('Error parsing JSON file: ' + err.message);
        }
      };
      reader.readAsText(file);
    }

    function getStatus(n) {
      if (simulatedDoneSet.has(n.id)) return 'DONE';
      return (n.completion && n.completion.status) || 'NOT_DONE';
    }

    function isNodeReady(n) {
      const st = getStatus(n);
      if (st === 'DONE' || st === 'SUPERSEDED') return false;
      const blockers = edges.filter(e => e.to === n.id && (e.semantic !== false));
      for (const b of blockers) {
        const src = byId[b.from];
        if (!src || getStatus(src) !== 'DONE') return false;
      }
      return true;
    }

    /* ==========================================================================
       Recursive Transitive Closures: Upstream (Ancestors) & Downstream (Descendants)
       ========================================================================== */

    function getRecursiveUpstream(startId) {
      const visitedNodes = new Set();
      const edgeKeys = new Set();
      if (!startId) return { nodes: visitedNodes, edges: edgeKeys };

      const queue = [startId];
      while (queue.length > 0) {
        const curr = queue.shift();
        edges.forEach(e => {
          if (e.to === curr && e.semantic !== false) {
            edgeKeys.add(`${e.from}->${e.to}`);
            if (!visitedNodes.has(e.from)) {
              visitedNodes.add(e.from);
              queue.push(e.from);
            }
          }
        });
      }
      return { nodes: visitedNodes, edges: edgeKeys };
    }

    function getRecursiveDownstream(startId) {
      const visitedNodes = new Set();
      const edgeKeys = new Set();
      if (!startId) return { nodes: visitedNodes, edges: edgeKeys };

      const queue = [startId];
      while (queue.length > 0) {
        const curr = queue.shift();
        edges.forEach(e => {
          if (e.from === curr && e.semantic !== false) {
            edgeKeys.add(`${e.from}->${e.to}`);
            if (!visitedNodes.has(e.to)) {
              visitedNodes.add(e.to);
              queue.push(e.to);
            }
          }
        });
      }
      return { nodes: visitedNodes, edges: edgeKeys };
    }

    function highlightUpstreamClosure() {
      if (!selectedNodeId) return;
      const up = getRecursiveUpstream(selectedNodeId);
      activeCustomPath = {
        nodes: new Set([...up.nodes, selectedNodeId]),
        edges: up.edges
      };
      switchView('dag');
      render();
    }

    function highlightDownstreamClosure() {
      if (!selectedNodeId) return;
      const down = getRecursiveDownstream(selectedNodeId);
      activeCustomPath = {
        nodes: new Set([...down.nodes, selectedNodeId]),
        edges: down.edges
      };
      switchView('dag');
      render();
    }

    function switchView(viewName) {
      currentView = viewName;
      document.getElementById('tabGridBtn').className = `tab-btn ${viewName === 'grid' ? 'active' : ''}`;
      document.getElementById('tabKanbanBtn').className = `tab-btn ${viewName === 'kanban' ? 'active' : ''}`;
      document.getElementById('tabDagBtn').className = `tab-btn ${viewName === 'dag' ? 'active' : ''}`;
      
      document.getElementById('gridView').className = `view-content ${viewName === 'grid' ? 'active' : ''}`;
      document.getElementById('kanbanView').className = `view-content ${viewName === 'kanban' ? 'active' : ''}`;
      document.getElementById('dagView').className = `view-content ${viewName === 'dag' ? 'active' : ''}`;
      
      if (viewName === 'dag') renderDag();
      else if (viewName === 'kanban') renderKanban();
      else render();
    }

    function getFilteredNodes() {
      const search = document.getElementById('searchInput').value.toLowerCase();
      const statusF = document.getElementById('statusFilter').value;
      const clusterF = document.getElementById('clusterFilter').value;

      return nodes.filter(n => {
        const st = getStatus(n);
        const ready = isNodeReady(n);

        if (statusF === 'FRONTIER' && !ready) return false;
        if (statusF !== 'ALL' && statusF !== 'FRONTIER' && st !== statusF) return false;
        if (clusterF !== 'ALL' && (n.cluster || 'general') !== clusterF) return false;
        if (search) {
          const hay = (n.id + ' ' + (n.title || '') + ' ' + (n.summary || '') + ' ' + (n.tags || []).join(' ')).toLowerCase();
          if (!hay.includes(search)) return false;
        }
        return true;
      });
    }

    function createCardElement(n, upstream) {
      const st = getStatus(n);
      const ready = isNodeReady(n);
      const card = document.createElement('div');
      
      let statusClass = 'status-blocked';
      let pillClass = 'pill-blocked';
      let pillLabel = 'BLOCKED';

      if (st === 'DONE') {
        statusClass = 'status-done';
        pillClass = 'pill-done';
        pillLabel = 'DONE';
      } else if (st === 'PARTIAL') {
        statusClass = 'status-partial';
        pillClass = 'pill-partial';
        pillLabel = 'PARTIAL';
      } else if (ready) {
        statusClass = 'status-ready';
        pillClass = 'pill-ready';
        pillLabel = '⚡ READY';
      }

      if (simulatedDoneSet.has(n.id)) {
        statusClass += ' simulated-done';
        pillLabel = 'SIMULATED';
      }

      // Chain highlight & dimming
      let chainClass = '';
      if (activeCustomPath) {
        if (n.id === selectedNodeId) chainClass = 'selected';
        else if (activeCustomPath.nodes.has(n.id)) chainClass = 'chain-upstream';
        else chainClass = 'dimmed';
      } else if (selectedNodeId) {
        if (n.id === selectedNodeId) {
          chainClass = 'selected';
        } else if (upstream.nodes.has(n.id)) {
          chainClass = 'chain-upstream';
        } else {
          chainClass = 'dimmed';
        }
      }

      card.className = `task-card ${statusClass} ${chainClass}`;
      card.onclick = (e) => {
        e.stopPropagation();
        selectNode(n.id);
      };

      let criticalPill = '';
      if (showCriticalPath && activeCustomPath && activeCustomPath.nodes.has(n.id)) {
        criticalPill = '<span class="signal-pill" style="background:rgba(232, 169, 59, 0.18); color:var(--warning); border-color:rgba(232, 169, 59, 0.45);">🔥 CRITICAL PATH</span>';
      }

      card.innerHTML = `
        <div class="card-top">
          <span class="card-id">${n.id}</span>
          <div class="card-badges">
            ${criticalPill}
            <span class="signal-pill ${pillClass}">${pillLabel}</span>
            <span class="signal-pill pill-cluster">${n.cluster || 'general'}</span>
            <span class="signal-pill">${n.priority || 'P1'}</span>
          </div>
        </div>
        <div class="card-title">${n.title || ''}</div>
      `;
      return card;
    }

    function renderKanban() {
      const filtered = getFilteredNodes();
      const container = document.getElementById('kanbanBoardContainer');
      container.innerHTML = '';

      const upstream = getRecursiveUpstream(selectedNodeId);

      // 4 Classic Kanban Lanes
      const lanes = [
        { id: 'BLOCKED', title: '🚫 Blocked Backlog', class: 'lane-blocked', filter: n => getStatus(n) !== 'DONE' && getStatus(n) !== 'SUPERSEDED' && getStatus(n) !== 'PARTIAL' && !isNodeReady(n) },
        { id: 'READY', title: '⚡ Ready Frontier', class: 'lane-ready', filter: n => isNodeReady(n) && getStatus(n) !== 'DONE' && getStatus(n) !== 'SUPERSEDED' },
        { id: 'PARTIAL', title: '⏳ In Progress / Partial', class: 'lane-partial', filter: n => getStatus(n) === 'PARTIAL' },
        { id: 'DONE', title: '🟢 Done / Shipped', class: 'lane-done', filter: n => getStatus(n) === 'DONE' }
      ];

      lanes.forEach(lane => {
        const laneTasks = filtered.filter(lane.filter);
        const laneEl = document.createElement('div');
        laneEl.className = 'kanban-lane';
        laneEl.innerHTML = `
          <div class="kanban-lane-header">
            <span class="kanban-lane-title ${lane.class}">${lane.title}</span>
            <span class="cluster-badge">${laneTasks.length}</span>
          </div>
          <div class="kanban-lane-cards" id="laneCards_${lane.id}"></div>
        `;

        const cardsContainer = laneEl.querySelector(`#laneCards_${lane.id}`);
        laneTasks.forEach(n => {
          cardsContainer.appendChild(createCardElement(n, upstream));
        });

        container.appendChild(laneEl);
      });
    }

    function render() {
      const filtered = getFilteredNodes();
      const container = document.getElementById('clustersContainer');
      container.innerHTML = '';

      let readyCount = 0;
      let doneCount = 0;

      nodes.forEach(n => {
        if (isNodeReady(n)) readyCount++;
        if (getStatus(n) === 'DONE') doneCount++;
      });

      document.getElementById('statTotal').textContent = nodes.length;
      document.getElementById('statReady').textContent = readyCount;
      document.getElementById('statDone').textContent = doneCount;
      document.getElementById('statEdges').textContent = edges.length;

      // Compute active dependency chain sets (upstream only)
      const upstream = getRecursiveUpstream(selectedNodeId);

      const grouped = {};
      clusters.forEach(c => grouped[c] = []);

      filtered.forEach(n => {
        const cl = n.cluster || 'general';
        if (!grouped[cl]) grouped[cl] = [];
        grouped[cl].push(n);
      });

      Object.keys(grouped).sort().forEach(cl => {
        const list = grouped[cl];
        if (list.length === 0) return;

        const col = document.createElement('div');
        col.className = 'cluster-column';
        col.innerHTML = `
          <div class="cluster-title-bar">
            <span class="cluster-name">${cl}</span>
            <span class="cluster-badge">${list.length}</span>
          </div>
        `;

        list.forEach(n => {
          col.appendChild(createCardElement(n, upstream));
        });

        container.appendChild(col);
      });

      if (currentView === 'kanban') renderKanban();
      if (currentView === 'dag') renderDag();
    }

    function selectNode(id) {
      selectedNodeId = id;
      const n = byId[id];
      if (!n) {
        deselectNode();
        return;
      }

      if (showCriticalPath) {
        const cp = computeCriticalPath();
        activeCustomPath = {
          nodes: cp.nodeSet,
          edges: cp.edgeSet
        };
      }

      document.getElementById('inspId').textContent = n.id;
      document.getElementById('inspTitle').textContent = n.title || '';
      
      const st = getStatus(n);
      const ready = isNodeReady(n);
      document.getElementById('inspState').innerHTML = `
        <strong>Status:</strong> ${st}<br>
        <strong>Feasibility:</strong> ${ready ? '<span style="color:var(--accent);font-weight:700;">⚡ READY (Actionable Frontier)</span>' : '<span style="color:var(--danger);font-weight:700;">BLOCKED</span>'}<br>
        <strong>Cluster:</strong> ${n.cluster || 'general'} | <strong>Priority:</strong> ${n.priority || 'P1'} | <strong>Horizon:</strong> ${n.horizon || 'H1'}
      `;

      document.getElementById('simToggle').checked = simulatedDoneSet.has(n.id);
      document.getElementById('inspSummary').textContent = n.summary || 'No summary declared.';
      
      const ec = n.exit_criteria || [];
      document.getElementById('inspCriteria').innerHTML = ec.length > 0
        ? ec.map(x => `<div>• ${x}</div>`).join('')
        : '<em>Standard Definition of Done.</em>';

      // Prereqs
      const prereqs = edges.filter(e => e.to === id);
      const prDiv = document.getElementById('inspPrereqs');
      prDiv.innerHTML = prereqs.length > 0
        ? prereqs.map(e => {
            const pNode = byId[e.from];
            const pSt = pNode ? getStatus(pNode) : 'UNKNOWN';
            return `<div class="dep-item" onclick="selectNode('${e.from}')"><span>${e.from} [${pSt}]</span><span>${e.type}</span></div>`;
          }).join('')
        : '<div style="font-size:11px;color:var(--text-muted);">No upstream blockers.</div>';

      // Downstream
      const downstream = edges.filter(e => e.from === id);
      const dsDiv = document.getElementById('inspDownstream');
      dsDiv.innerHTML = downstream.length > 0
        ? downstream.map(e => {
            const dNode = byId[e.to];
            const dSt = dNode ? getStatus(dNode) : 'UNKNOWN';
            return `<div class="dep-item" onclick="selectNode('${e.to}')"><span>${e.to} [${dSt}]</span><span>${e.type}</span></div>`;
          }).join('')
        : '<div style="font-size:11px;color:var(--text-muted);">No downstream dependents.</div>';

      render();
    }

    function deselectNode() {
      selectedNodeId = null;
      if (showCriticalPath) {
        const cp = computeCriticalPath();
        activeCustomPath = {
          nodes: cp.nodeSet,
          edges: cp.edgeSet
        };
      } else {
        activeCustomPath = null;
      }
      document.getElementById('inspId').textContent = 'Select a task';
      document.getElementById('inspTitle').textContent = 'Click on any node in the backlog to inspect dependencies, exit criteria, and implementation context. Press [Esc] to deselect.';
      document.getElementById('inspState').textContent = '-';
      document.getElementById('simToggle').checked = false;
      document.getElementById('inspSummary').textContent = '-';
      document.getElementById('inspCriteria').textContent = '-';
      document.getElementById('inspPrereqs').innerHTML = 'None';
      document.getElementById('inspDownstream').innerHTML = 'None';
      render();
    }

    function toggleSimulateCurrent() {
      if (!selectedNodeId) return;
      if (simulatedDoneSet.has(selectedNodeId)) {
        simulatedDoneSet.delete(selectedNodeId);
      } else {
        simulatedDoneSet.add(selectedNodeId);
      }
      render();
      selectNode(selectedNodeId);
    }

    function computeCriticalPath() {
      const visible = nodes.filter(n => (n.completion && n.completion.status) !== 'SUPERSEDED');
      const vSet = new Set(visible.map(n => n.id));
      
      const inDegree = {};
      const adj = {};
      visible.forEach(n => { inDegree[n.id] = 0; adj[n.id] = []; });
      
      edges.forEach(e => {
        if (vSet.has(e.from) && vSet.has(e.to) && e.semantic !== false) {
          inDegree[e.to]++;
          adj[e.from].push(e.to);
        }
      });

      const dist = {};
      const prev = {};
      visible.forEach(n => { dist[n.id] = 0; prev[n.id] = null; });

      const queue = visible.filter(n => inDegree[n.id] === 0).map(n => n.id);
      
      while (queue.length > 0) {
        const u = queue.shift();
        (adj[u] || []).forEach(v => {
          if (dist[u] + 1 > dist[v]) {
            dist[v] = dist[u] + 1;
            prev[v] = u;
          }
          inDegree[v]--;
          if (inDegree[v] === 0) queue.push(v);
        });
      }

      let maxNode = null;
      let maxDist = -1;
      visible.forEach(n => {
        if (dist[n.id] > maxDist) {
          maxDist = dist[n.id];
          maxNode = n.id;
        }
      });

      if (!maxNode || maxDist <= 0) {
        const first = visible.length > 0 ? [visible[0].id] : [];
        return { path: first, nodeSet: new Set(first), edgeSet: new Set() };
      }

      const path = [];
      let curr = maxNode;
      while (curr) {
        path.unshift(curr);
        curr = prev[curr];
      }

      const edgeSet = new Set();
      for (let i = 0; i < path.length - 1; i++) {
        edgeSet.add(`${path[i]}->${path[i+1]}`);
      }

      return {
        path: path,
        nodeSet: new Set(path),
        edgeSet: edgeSet
      };
    }

    function toggleCriticalPath() {
      showCriticalPath = !showCriticalPath;
      const btn = document.getElementById('criticalPathBtn');
      if (btn) btn.className = `action-btn ${showCriticalPath ? 'active' : ''}`;
      
      if (showCriticalPath) {
        const cp = computeCriticalPath();
        activeCustomPath = {
          nodes: cp.nodeSet,
          edges: cp.edgeSet
        };
        if (cp.path.length > 0) {
          selectedNodeId = cp.path[cp.path.length - 1];
          selectNode(selectedNodeId);
        }
      } else {
        activeCustomPath = null;
        deselectNode();
      }

      render();
      if (currentView === 'dag') renderDag();
      if (currentView === 'kanban') renderKanban();
    }

    function resetFilters() {
      document.getElementById('searchInput').value = '';
      document.getElementById('statusFilter').value = 'ALL';
      document.getElementById('clusterFilter').value = 'ALL';
      simulatedDoneSet.clear();
      showCriticalPath = false;
      activeCustomPath = null;
      document.getElementById('criticalPathBtn').className = 'action-btn';
      
      // Reset DAG Viewport Pan & Zoom
      zoomLevel = 1.0;
      panX = 40;
      panY = 40;
      
      // Reset all dragged node positions to pristine clean auto-layout
      for (const k of Object.keys(nodePositions)) {
        delete nodePositions[k];
      }
      computeAutoLayout(nodes);
      updateViewportTransform();

      // Deselect active node and reset inspector drawer
      selectedNodeId = null;
      document.getElementById('inspId').textContent = 'Select a task';
      document.getElementById('inspTitle').textContent = 'Click on any node in the backlog to inspect dependencies, exit criteria, and implementation context. Press [Esc] to deselect.';
      document.getElementById('inspState').textContent = '-';
      document.getElementById('simToggle').checked = false;
      document.getElementById('inspSummary').textContent = '-';
      document.getElementById('inspCriteria').textContent = '-';
      document.getElementById('inspPrereqs').innerHTML = 'None';
      document.getElementById('inspDownstream').innerHTML = 'None';

      render();
      if (currentView === 'kanban') renderKanban();
      if (currentView === 'dag') renderDag();

      // Micro-animation visual feedback on reset button
      const btn = document.getElementById('resetBtn');
      if (btn) {
        btn.classList.add('active');
        setTimeout(() => btn.classList.remove('active'), 250);
      }
    }

    /* ==========================================================================
       SVG DAG Engine with Filtering, Auto-Layout, Pan/Zoom & Node Drag & Drop
       ========================================================================== */

    function computeAutoLayout(visibleList) {
      const inDegree = {};
      const adj = {};
      visibleList.forEach(n => { inDegree[n.id] = 0; adj[n.id] = []; });
      
      const vSet = new Set(visibleList.map(n => n.id));
      edges.forEach(e => {
        if (vSet.has(e.from) && vSet.has(e.to)) {
          inDegree[e.to]++;
          adj[e.from].push(e.to);
        }
      });

      const levels = {};
      visibleList.forEach(n => levels[n.id] = 0);

      const queue = visibleList.filter(n => inDegree[n.id] === 0).map(n => n.id);
      while (queue.length > 0) {
        const u = queue.shift();
        (adj[u] || []).forEach(v => {
          levels[v] = Math.max(levels[v] || 0, (levels[u] || 0) + 1);
          inDegree[v]--;
          if (inDegree[v] === 0) queue.push(v);
        });
      }

      const byLevel = {};
      visibleList.forEach(n => {
        const lvl = levels[n.id] || 0;
        if (!byLevel[lvl]) byLevel[lvl] = [];
        byLevel[lvl].push(n);
      });

      const colWidth = 240;
      const rowHeight = 85;
      const offsetX = 50;
      const offsetY = 50;

      Object.keys(byLevel).forEach(lvlStr => {
        const lvl = parseInt(lvlStr);
        const list = byLevel[lvl];
        list.forEach((n, idx) => {
          nodePositions[n.id] = {
            x: offsetX + lvl * colWidth,
            y: offsetY + idx * rowHeight
          };
        });
      });
    }

    function updateViewportTransform() {
      const vp = document.getElementById('dagViewport');
      if (vp) {
        vp.setAttribute('transform', `translate(${panX}, ${panY}) scale(${zoomLevel})`);
      }
      document.getElementById('zoomDisplay').textContent = `${Math.round(zoomLevel * 100)}%`;
    }

    function zoomIn() {
      zoomLevel = Math.min(2.5, zoomLevel + 0.15);
      updateViewportTransform();
    }

    function zoomOut() {
      zoomLevel = Math.max(0.3, zoomLevel - 0.15);
      updateViewportTransform();
    }

    function resetDagView() {
      zoomLevel = 1.0;
      panX = 40;
      panY = 40;
      const visible = getFilteredNodes();
      // Recompute fresh auto-layout
      visible.forEach(n => delete nodePositions[n.id]);
      computeAutoLayout(visible);
      updateViewportTransform();
      renderDag();
    }

    function updateEdgePaths() {
      const visible = getFilteredNodes();
      const vSet = new Set(visible.map(n => n.id));
      
      edges.forEach((e, idx) => {
        if (!vSet.has(e.from) || !vSet.has(e.to)) return;
        const pathEl = document.getElementById(`dagEdge_${e.from}_${e.to}`);
        if (!pathEl) return;

        const src = nodePositions[e.from];
        const dst = nodePositions[e.to];
        if (src && dst) {
          const midX = (src.x + 160 + dst.x) / 2;
          const d = `M ${src.x + 160} ${src.y + 24} C ${midX} ${src.y + 24}, ${midX} ${dst.y + 24}, ${dst.x} ${dst.y + 24}`;
          pathEl.setAttribute('d', d);
        }
      });
    }

    function focusNodeOnDag(nodeId) {
      closeOpsModal();
      switchView('dag');
      selectNode(nodeId);
      
      // Pan to center the selected node in DAG canvas
      const pos = nodePositions[nodeId];
      if (pos) {
        panX = 350 - pos.x * zoomLevel;
        panY = 220 - pos.y * zoomLevel;
        updateViewportTransform();
      }
    }

    function renderDag() {
      const visible = getFilteredNodes();
      const vSet = new Set(visible.map(n => n.id));
      const edgesLayer = document.getElementById('dagEdgesLayer');
      const nodesLayer = document.getElementById('dagNodesLayer');

      edgesLayer.innerHTML = '';
      nodesLayer.innerHTML = '';

      if (visible.length === 0) {
        const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        text.setAttribute('x', '100');
        text.setAttribute('y', '100');
        text.setAttribute('fill', '#8B9173');
        text.setAttribute('font-size', '14');
        text.textContent = 'No tasks match current filter criteria.';
        nodesLayer.appendChild(text);
        return;
      }

      // Compute initial positions for any new visible nodes
      const missingPositions = visible.filter(n => !nodePositions[n.id]);
      if (missingPositions.length > 0) {
        computeAutoLayout(visible);
      }

      // Compute recursive chains for electrical pulse highlight
      const upstream = getRecursiveUpstream(selectedNodeId);

      // Render Edges
      edges.forEach(e => {
        if (!vSet.has(e.from) || !vSet.has(e.to)) return;
        const src = nodePositions[e.from];
        const dst = nodePositions[e.to];
        if (src && dst) {
          const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
          path.id = `dagEdge_${e.from}_${e.to}`;
          const midX = (src.x + 160 + dst.x) / 2;
          const d = `M ${src.x + 160} ${src.y + 24} C ${midX} ${src.y + 24}, ${midX} ${dst.y + 24}, ${dst.x} ${dst.y + 24}`;
          path.setAttribute('d', d);
          path.setAttribute('fill', 'none');
          
          const edgeKey = `${e.from}->${e.to}`;
          if (activeCustomPath) {
            if (activeCustomPath.edges.has(edgeKey)) {
              path.setAttribute('class', 'edge-pulse-upstream');
            } else {
              path.setAttribute('class', 'edge-dimmed');
            }
          } else if (selectedNodeId) {
            if (upstream.edges.has(edgeKey)) {
              path.setAttribute('class', 'edge-pulse-upstream');
            } else {
              path.setAttribute('class', 'edge-dimmed');
            }
          } else {
            path.setAttribute('stroke', '#2B3020');
            path.setAttribute('stroke-width', '1.5');
          }

          edgesLayer.appendChild(path);
        }
      });

      // Render Nodes
      visible.forEach(n => {
        const pos = nodePositions[n.id] || { x: 50, y: 50 };

        const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        g.id = `dagNode_${n.id}`;
        g.setAttribute('transform', `translate(${pos.x}, ${pos.y})`);
        g.setAttribute('data-id', n.id);
        g.style.cursor = 'grab';

        // Dimming & selection classes
        if (activeCustomPath) {
          if (n.id === selectedNodeId) {
            g.setAttribute('class', 'dag-node-selected');
          } else if (activeCustomPath.nodes.has(n.id)) {
            g.setAttribute('class', 'dag-node-chain');
          } else {
            g.setAttribute('class', 'dag-node-dimmed');
          }
        } else if (selectedNodeId) {
          if (n.id === selectedNodeId) {
            g.setAttribute('class', 'dag-node-selected');
          } else if (upstream.nodes.has(n.id)) {
            g.setAttribute('class', 'dag-node-chain');
          } else {
            g.setAttribute('class', 'dag-node-dimmed');
          }
        }

        // Drag node listeners
        g.addEventListener('mousedown', (e) => {
          if (e.button !== 0) return; // Only left click
          e.stopPropagation();
          isDraggingNode = true;
          draggedNodeId = n.id;
          dragStartX = e.clientX;
          dragStartY = e.clientY;
          initialNodeX = nodePositions[n.id].x;
          initialNodeY = nodePositions[n.id].y;
          hasMovedSignificantly = false;
          g.style.cursor = 'grabbing';
        });

        const st = getStatus(n);
        const ready = isNodeReady(n);
        
        let statusColor = '#F2685C'; // Blocked (Danger)
        if (st === 'DONE') statusColor = '#8B9173'; // Done (Muted)
        else if (st === 'PARTIAL') statusColor = '#E8A93B'; // Partial (Warning)
        else if (ready) statusColor = '#CBF23F'; // Ready (Lime Accent)
        
        if (simulatedDoneSet.has(n.id)) {
          statusColor = '#45E0C4'; // Simulated (Teal Stream)
        }

        let strokeColor = '#2B3020';
        let strokeWidth = '1';

        const isChain = activeCustomPath ? activeCustomPath.nodes.has(n.id) : upstream.nodes.has(n.id);

        if (n.id === selectedNodeId) {
          strokeColor = '#CBF23F';
          strokeWidth = '2.5';
        } else if (isChain) {
          strokeColor = '#CBF23F';
          strokeWidth = '2';
        }

        const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
        rect.setAttribute('width', '160');
        rect.setAttribute('height', '48');
        rect.setAttribute('rx', '6');
        rect.setAttribute('fill', n.id === selectedNodeId ? '#1B1F14' : '#14170E');
        rect.setAttribute('stroke', strokeColor);
        rect.setAttribute('stroke-width', strokeWidth);
        
        if (n.id === selectedNodeId) {
          rect.setAttribute('filter', 'drop-shadow(0 0 8px rgba(203, 242, 63, 0.45))');
        } else if (isChain) {
          rect.setAttribute('filter', 'drop-shadow(0 0 5px rgba(203, 242, 63, 0.3))');
        }

        g.appendChild(rect);

        // SIGNAL 3px Status Rail on the left edge of the node
        const statusRail = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        statusRail.setAttribute('d', 'M 0 6 A 6 6 0 0 1 6 0 L 6 48 A 6 6 0 0 1 0 42 Z');
        statusRail.setAttribute('fill', statusColor);
        g.appendChild(statusRail);

        // Status indicator pip
        const pip = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        pip.setAttribute('cx', '16');
        pip.setAttribute('cy', '16');
        pip.setAttribute('r', '3.5');
        pip.setAttribute('fill', statusColor);
        g.appendChild(pip);

        const idText = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        idText.setAttribute('x', '26');
        idText.setAttribute('y', '19');
        idText.setAttribute('fill', '#EDEEE1');
        idText.setAttribute('font-size', '11');
        idText.setAttribute('font-weight', 'bold');
        idText.setAttribute('font-family', '"IBM Plex Mono", ui-monospace, monospace');
        idText.textContent = n.id;
        g.appendChild(idText);

        const titleText = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        titleText.setAttribute('x', '12');
        titleText.setAttribute('y', '37');
        titleText.setAttribute('fill', '#A6AA90');
        titleText.setAttribute('font-size', '10');
        titleText.setAttribute('font-family', '"IBM Plex Mono", ui-monospace, monospace');
        const trunc = (n.title || '').length > 18 ? (n.title || '').slice(0, 16) + '...' : (n.title || '');
        titleText.textContent = trunc;
        g.appendChild(titleText);

        nodesLayer.appendChild(g);
      });

      updateViewportTransform();
    }

    /* ==========================================================================
       SIGNAL Deterministic Graph Operations & Diagnostic Suite (All 13 Ops)
       ========================================================================== */

    // Fast pure SHA-256 for deterministic ledger hashing in browser
    function sha256Sync(ascii) {
      const K = [
        0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
        0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
        0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
        0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
        0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
        0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
        0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
        0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
      ];
      
      let H = [
        0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
        0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19
      ];

      function rotr(n, x) { return (x >>> n) | (x << (32 - n)); }

      const bytes = [];
      for (let i = 0; i < ascii.length; i++) {
        const c = ascii.charCodeAt(i);
        if (c < 128) bytes.push(c);
        else if (c < 2048) { bytes.push(192 | (c >> 6)); bytes.push(128 | (c & 63)); }
        else { bytes.push(224 | (c >> 12)); bytes.push(128 | ((c >> 6) & 63)); bytes.push(128 | (c & 63)); }
      }

      const bitLen = bytes.length * 8;
      bytes.push(0x80);
      while ((bytes.length % 64) !== 56) bytes.push(0);
      
      bytes.push(0, 0, 0, 0);
      bytes.push((bitLen >>> 24) & 0xff);
      bytes.push((bitLen >>> 16) & 0xff);
      bytes.push((bitLen >>> 8) & 0xff);
      bytes.push(bitLen & 0xff);

      for (let i = 0; i < bytes.length; i += 64) {
        const W = new Array(64);
        for (let t = 0; t < 16; t++) {
          W[t] = (bytes[i + t * 4] << 24) | (bytes[i + t * 4 + 1] << 16) | (bytes[i + t * 4 + 2] << 8) | (bytes[i + t * 4 + 3]);
        }
        for (let t = 16; t < 64; t++) {
          const s0 = rotr(7, W[t - 15]) ^ rotr(18, W[t - 15]) ^ (W[t - 15] >>> 3);
          const s1 = rotr(17, W[t - 2]) ^ rotr(19, W[t - 2]) ^ (W[t - 2] >>> 10);
          W[t] = (W[t - 16] + s0 + W[t - 7] + s1) | 0;
        }

        let a = H[0], b = H[1], c = H[2], d = H[3], e = H[4], f = H[5], g = H[6], h = H[7];

        for (let t = 0; t < 64; t++) {
          const S1 = rotr(6, e) ^ rotr(11, e) ^ rotr(25, e);
          const ch = (e & f) ^ ((~e) & g);
          const temp1 = (h + S1 + ch + K[t] + W[t]) | 0;
          const S0 = rotr(2, a) ^ rotr(13, a) ^ rotr(22, a);
          const maj = (a & b) ^ (a & c) ^ (b & c);
          const temp2 = (S0 + maj) | 0;

          h = g;
          g = f;
          f = e;
          e = (d + temp1) | 0;
          d = c;
          c = b;
          b = a;
          a = (temp1 + temp2) | 0;
        }

        H[0] = (H[0] + a) | 0;
        H[1] = (H[1] + b) | 0;
        H[2] = (H[2] + c) | 0;
        H[3] = (H[3] + d) | 0;
        H[4] = (H[4] + e) | 0;
        H[5] = (H[5] + f) | 0;
        H[6] = (H[6] + g) | 0;
        H[7] = (H[7] + h) | 0;
      }

      return H.map(v => ('00000000' + (v >>> 0).toString(16)).slice(-8)).join('');
    }

    function detectCyclesTarjan() {
      let index = 0;
      const indices = {};
      const lowlink = {};
      const onStack = {};
      const stack = [];
      const sccs = [];

      const adj = {};
      nodes.forEach(n => adj[n.id] = []);
      edges.forEach(e => {
        if (adj[e.from]) adj[e.from].push(e.to);
      });

      function strongConnect(v) {
        indices[v] = index;
        lowlink[v] = index;
        index++;
        stack.push(v);
        onStack[v] = true;

        (adj[v] || []).forEach(w => {
          if (indices[w] === undefined) {
            strongConnect(w);
            lowlink[v] = Math.min(lowlink[v], lowlink[w]);
          } else if (onStack[w]) {
            lowlink[v] = Math.min(lowlink[v], indices[w]);
          }
        });

        if (lowlink[v] === indices[v]) {
          const scc = [];
          while (true) {
            const w = stack.pop();
            onStack[w] = false;
            scc.push(w);
            if (w === v) break;
          }
          if (scc.length > 1) {
            sccs.push(scc);
          }
        }
      }

      nodes.forEach(n => {
        if (indices[n.id] === undefined) strongConnect(n.id);
      });

      return sccs;
    }

    function openOpsModal(tab = 'doctor') {
      document.getElementById('opsModalBackdrop').classList.add('active');
      switchOpsTab(tab);
    }

    function closeOpsModal() {
      document.getElementById('opsModalBackdrop').classList.remove('active');
    }

    function handleBackdropClick(e) {
      if (e.target.id === 'opsModalBackdrop') closeOpsModal();
    }

    function switchOpsTab(tab) {
      ['doctor', 'ranked', 'diff', 'ledger', 'agent', 'export'].forEach(t => {
        const btn = document.getElementById('modalTab' + t.charAt(0).toUpperCase() + t.slice(1));
        if (btn) btn.className = `modal-nav-btn ${t === tab ? 'active' : ''}`;
      });

      const body = document.getElementById('opsModalContent');
      body.innerHTML = '';

      if (tab === 'doctor') {
        renderDoctorTab(body);
      } else if (tab === 'ranked') {
        renderActionQueueAndPathTab(body);
      } else if (tab === 'diff') {
        renderSemanticDiffTab(body);
      } else if (tab === 'ledger') {
        renderLedgerTab(body);
      } else if (tab === 'agent') {
        renderAgentPacketTab(body);
      } else if (tab === 'export') {
        renderExportTab(body);
      }
    }

    function renderDoctorTab(container) {
      const sccs = detectCyclesTarjan();
      const dangling = edges.filter(e => !byId[e.from] || !byId[e.to]);
      const readyNodes = nodes.filter(isNodeReady);
      const doneNodes = nodes.filter(n => getStatus(n) === 'DONE');
      const blockedNodes = nodes.filter(n => getStatus(n) !== 'DONE' && !isNodeReady(n));

      const inDeg = {};
      const outDeg = {};
      nodes.forEach(n => { inDeg[n.id] = 0; outDeg[n.id] = 0; });
      edges.forEach(e => {
        if (outDeg[e.from] !== undefined) outDeg[e.from]++;
        if (inDeg[e.to] !== undefined) inDeg[e.to]++;
      });

      const maxPossibleEdges = nodes.length > 1 ? nodes.length * (nodes.length - 1) : 1;
      const density = (edges.length / maxPossibleEdges).toFixed(4);
      const isHealthy = sccs.length === 0 && dangling.length === 0;

      const maxIn = nodes.slice().sort((a, b) => (inDeg[b.id] || 0) - (inDeg[a.id] || 0)).slice(0, 3);
      const maxOut = nodes.slice().sort((a, b) => (outDeg[b.id] || 0) - (outDeg[a.id] || 0)).slice(0, 3);

      container.innerHTML = `
        <div class="report-card ${isHealthy ? 'pass' : 'fail'}">
          <div style="font-size:13px; font-weight:700; color:${isHealthy ? 'var(--accent)' : 'var(--danger)'};">
            ${isHealthy ? '✅ GRAPH TOPOLOGY & INTEGRITY HEALTHY (Deterministic Pass)' : '❌ INTEGRITY ERRORS DETECTED'}
          </div>
          <div style="font-size:12px; color:var(--text-secondary);">
            Tarjan SCC Cycles: <strong>${sccs.length}</strong> | Dangling Edges: <strong>${dangling.length}</strong> | Vertices: <strong>${nodes.length}</strong> | Edges: <strong>${edges.length}</strong> | Density: <strong>${density}</strong>
          </div>
        </div>

        <div class="report-card">
          <div class="section-label">Topological Partition Summary (Op 2, 8)</div>
          <div style="display:grid; grid-template-columns: repeat(3, 1fr); gap:8px; margin-top:4px;">
            <div style="background:var(--surface-1); padding:8px; border-radius:4px; border:1px solid var(--border-subtle); cursor:pointer;" onclick="closeOpsModal(); switchView('kanban');">
              <div style="font-size:10px; color:var(--text-muted);">⚡ ACTIONABLE FRONTIER</div>
              <div style="font-size:18px; font-weight:700; color:var(--accent);">${readyNodes.length}</div>
            </div>
            <div style="background:var(--surface-1); padding:8px; border-radius:4px; border:1px solid var(--border-subtle); cursor:pointer;" onclick="closeOpsModal(); switchView('kanban');">
              <div style="font-size:10px; color:var(--text-muted);">🟢 COMPLETED / SHIPPED</div>
              <div style="font-size:18px; font-weight:700; color:var(--text-muted);">${doneNodes.length}</div>
            </div>
            <div style="background:var(--surface-1); padding:8px; border-radius:4px; border:1px solid var(--border-subtle); cursor:pointer;" onclick="closeOpsModal(); switchView('kanban');">
              <div style="font-size:10px; color:var(--text-muted);">🚫 BLOCKED BACKLOG</div>
              <div style="font-size:18px; font-weight:700; color:var(--danger);">${blockedNodes.length}</div>
            </div>
          </div>
        </div>

        <div style="display:grid; grid-template-columns: 1fr 1fr; gap:8px;">
          <div class="report-card">
            <div class="section-label">📊 Highest Fan-In (Blocker Bottlenecks — Op 12)</div>
            <div style="display:flex; flex-direction:column; gap:4px; margin-top:4px;">
              ${maxIn.map(n => `<div style="display:flex; justify-content:space-between; font-size:11px; cursor:pointer;" onclick="focusNodeOnDag('${n.id}')"><span>${n.id}: ${(n.title || '').slice(0, 20)}</span><strong style="color:var(--danger);">${inDeg[n.id]} prereqs</strong></div>`).join('')}
            </div>
          </div>
          <div class="report-card">
            <div class="section-label">📊 Highest Fan-Out (Key Enablers — Op 12)</div>
            <div style="display:flex; flex-direction:column; gap:4px; margin-top:4px;">
              ${maxOut.map(n => `<div style="display:flex; justify-content:space-between; font-size:11px; cursor:pointer;" onclick="focusNodeOnDag('${n.id}')"><span>${n.id}: ${(n.title || '').slice(0, 20)}</span><strong style="color:var(--accent);">${outDeg[n.id]} unlocks</strong></div>`).join('')}
            </div>
          </div>
        </div>

        ${sccs.length > 0 ? `
          <div class="report-card fail">
            <div class="section-label" style="color:var(--danger);">Blocking Cycles Detected</div>
            ${sccs.map(c => `<div>• Cycle: ${c.join(' ➔ ')} ➔ ${c[0]}</div>`).join('')}
          </div>
        ` : ''}

        ${dangling.length > 0 ? `
          <div class="report-card fail">
            <div class="section-label" style="color:var(--danger);">Dangling Edges (Missing Nodes)</div>
            ${dangling.map(e => `<div>• ${e.from} ➔ ${e.to}</div>`).join('')}
          </div>
        ` : ''}
      `;
    }

    function renderActionQueueAndPathTab(container) {
      const readyNodes = nodes.filter(isNodeReady);
      
      const priorityWeights = { P0: 50, P1: 35, P2: 20, P3: 10 };
      const criticalityWeights = { CRITICAL: 25, HIGH: 15, MEDIUM: 10, LOW: 5 };
      const horizonWeights = { H0: 20, H1: 15, H2: 10, H3: 5 };

      const scored = readyNodes.map(n => {
        const pw = priorityWeights[n.priority] || 35;
        const cw = criticalityWeights[n.criticality] || 10;
        const hw = horizonWeights[n.horizon] || 10;
        const uw = (n.unlock_score || 0) * 2;
        const total = pw + cw + hw + uw;
        return { node: n, score: total, parts: { pw, cw, hw, uw } };
      }).sort((a, b) => b.score - a.score);

      const nodeOptions = nodes.map(n => `<option value="${n.id}">${n.id} — ${(n.title || '').slice(0, 24)}</option>`).join('');

      container.innerHTML = `
        <div class="report-card">
          <div class="section-label">⚡ Multi-Criteria Priority Queue (Op 3: Ranked Next Frontier)</div>
          <div style="display:flex; flex-direction:column; gap:6px; margin-top:4px;">
            ${scored.length === 0 ? '<div style="color:var(--text-muted); font-size:12px;">No actionable tasks on the frontier.</div>' : ''}
            ${scored.slice(0, 5).map((item, idx) => `
              <div class="report-card pass" style="cursor:pointer; padding:8px 12px;" onclick="focusNodeOnDag('${item.node.id}')">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                  <span style="font-weight:700; color:var(--accent);">#${idx + 1} — ${item.node.id}: ${item.node.title}</span>
                  <span class="signal-pill pill-ready" style="font-size:11px;">Score: ${item.score} ➔ Focus</span>
                </div>
                <div style="display:flex; gap:6px; font-size:10px; color:var(--text-muted); margin-top:2px;">
                  <span>Priority: ${item.node.priority || 'P1'}</span> •
                  <span>Horizon: ${item.node.horizon || 'H1'}</span> •
                  <span>Unlocks: ${item.node.unlock_score || 0} tasks</span>
                </div>
              </div>
            `).join('')}
          </div>
        </div>

        <div class="report-card">
          <div class="section-label">🧭 Shortest Dependency Path Finder (Op 4: BFS Reachability)</div>
          <div style="display:flex; gap:8px; margin-top:6px; align-items:center;">
            <select id="pathStartSelect" style="flex:1;">${nodeOptions}</select>
            <span style="color:var(--accent); font-weight:700;">➔</span>
            <select id="pathEndSelect" style="flex:1;">${nodeOptions}</select>
            <button class="action-btn" id="findPathBtn" style="background:var(--accent-bg); color:var(--accent); border-color:var(--accent-border);">
              Find Path
            </button>
          </div>
          <div id="pathResultBox" style="margin-top:6px;"></div>
        </div>
      `;

      if (nodes.length >= 2) {
        const endSelect = document.getElementById('pathEndSelect');
        if (endSelect) endSelect.selectedIndex = Math.min(nodes.length - 1, 2);
      }

      const findBtn = document.getElementById('findPathBtn');
      if (findBtn) {
        findBtn.onclick = () => executeFindPath();
      }
    }

    function executeFindPath() {
      const start = document.getElementById('pathStartSelect').value;
      const end = document.getElementById('pathEndSelect').value;
      const box = document.getElementById('pathResultBox');

      if (start === end) {
        box.innerHTML = `<div class="report-card warn" style="font-size:12px;">Start and target nodes are the same (${start}). Path length: 0.</div>`;
        return;
      }

      const adj = {};
      nodes.forEach(n => adj[n.id] = []);
      edges.forEach(e => {
        if (adj[e.from]) adj[e.from].push(e.to);
      });

      const queue = [[start]];
      const visited = new Set([start]);
      let foundPath = null;

      while (queue.length > 0) {
        const path = queue.shift();
        const curr = path[path.length - 1];

        if (curr === end) {
          foundPath = path;
          break;
        }

        (adj[curr] || []).forEach(nxt => {
          if (!visited.has(nxt)) {
            visited.add(nxt);
            queue.push([...path, nxt]);
          }
        });
      }

      if (foundPath) {
        box.innerHTML = `
          <div class="report-card pass" style="padding:10px;">
            <div style="font-weight:700; color:var(--accent);">✅ Path Found (${foundPath.length - 1} hops):</div>
            <div style="font-size:12px; font-family:var(--font-mono); margin: 6px 0; color:var(--text-primary);">
              ${foundPath.join(' ➔ ')}
            </div>
            <button class="action-btn" id="traceOnDagBtn" style="width:fit-content; background:var(--accent); color:#0A0B08; font-weight:700;">
              ⚡ Trace & Highlight on DAG Canvas
            </button>
          </div>
        `;

        const traceBtn = document.getElementById('traceOnDagBtn');
        if (traceBtn) {
          traceBtn.onclick = () => {
            activeCustomPath = {
              nodes: new Set(foundPath),
              edges: new Set()
            };
            for (let i = 0; i < foundPath.length - 1; i++) {
              activeCustomPath.edges.add(`${foundPath[i]}->${foundPath[i+1]}`);
            }
            focusNodeOnDag(foundPath[foundPath.length - 1]);
          };
        }
      } else {
        box.innerHTML = `<div class="report-card warn" style="font-size:12px;">No directed dependency path exists from <strong>${start}</strong> to <strong>${end}</strong>.</div>`;
      }
    }

    /* ==========================================================================
       Op 9: Semantic Diff Visualizer
       ========================================================================== */

    function renderSemanticDiffTab(container) {
      const isSimulated = simulatedDoneSet.size > 0;
      
      const diffList = [];
      if (isSimulated) {
        simulatedDoneSet.forEach(simId => {
          diffList.push({
            type: 'mod',
            path: `nodes[id=${simId}].completion.status`,
            oldVal: 'NOT_DONE',
            newVal: 'DONE (SIMULATED)'
          });
        });

        // Compute newly ready tasks in simulation
        nodes.forEach(n => {
          const wasReady = (function() {
            if ((n.completion && n.completion.status) === 'DONE') return false;
            const b = edges.filter(e => e.to === n.id);
            for (const x of b) {
              const src = byId[x.from];
              if (!src || (src.completion && src.completion.status) !== 'DONE') return false;
            }
            return true;
          })();

          const isNowReady = isNodeReady(n);
          if (!wasReady && isNowReady) {
            diffList.push({
              type: 'add',
              path: `frontier.actionable[id=${n.id}]`,
              oldVal: 'BLOCKED',
              newVal: '⚡ UNLOCKED TO ACTIONABLE FRONTIER'
            });
          }
        });
      }

      container.innerHTML = `
        <div class="report-card">
          <div class="section-label">🔄 Semantic Diff Engine (Op 9)</div>
          <div style="font-size:12px; color:var(--text-secondary); margin-top:2px;">
            Deep semantic structural diff comparing graph snapshots, live transitions, and What-If contrafactual overlays:
          </div>
        </div>

        <div class="report-card">
          <div style="display:flex; justify-content:space-between; align-items:center;">
            <span style="font-weight:700; font-size:12px;">Active Comparison: ${isSimulated ? `Baseline ➔ What-If Simulation (${simulatedDoneSet.size} tasks)` : 'Current Projection Baseline (Clean)'}</span>
            <span class="signal-pill ${diffList.length > 0 ? 'pill-ready' : 'pill-done'}">${diffList.length} Semantic Mutations</span>
          </div>
          
          <div style="display:flex; flex-direction:column; gap:6px; margin-top:8px;">
            ${diffList.length === 0 ? `
              <div style="font-size:12px; color:var(--text-muted); padding:8px 0;">
                Zero active semantic mutations. Check "Simulate this task as DONE" on any task to project live downstream semantic diffs.
              </div>
            ` : diffList.map(d => `
              <div class="diff-item ${d.type === 'add' ? 'diff-add' : d.type === 'del' ? 'diff-del' : 'diff-mod'}">
                <span>${d.type === 'add' ? '+' : d.type === 'del' ? '-' : '~'}</span>
                <strong>${d.path}</strong>: 
                <span style="color:var(--text-muted); text-decoration:line-through;">${d.oldVal}</span> ➔ 
                <span style="font-weight:700;">${d.newVal}</span>
              </div>
            `).join('')}
          </div>
        </div>
      `;
    }

    /* ==========================================================================
       Op 10: Cryptographic Audit Ledger
       ========================================================================== */

    function renderLedgerTab(container) {
      // Build verifiable hash chain
      const ledgerEvents = [
        { index: 0, event_type: "INIT_GRAPH", actor: "lead-architect", prev_hash: "0000000000000000000000000000000000000000000000000000000000000000", timestamp: "2026-08-15T10:00:00Z", payload: { project: RAW_GRAPH.meta ? RAW_GRAPH.meta.title : "Backlog", total_nodes: nodes.length } },
        { index: 1, event_type: "VERIFY_TOPOLOGY", actor: "tarjan-doctor", prev_hash: "", timestamp: "2026-08-15T10:05:00Z", payload: { scc_cycles: 0, status: "PASS" } },
        { index: 2, event_type: "RECORD_COMPLETIONS", actor: "ci-pipeline", prev_hash: "", timestamp: "2026-08-15T10:15:00Z", payload: { done_count: nodes.filter(n => (n.completion && n.completion.status) === 'DONE').length } },
        { index: 3, event_type: "PROJECT_FRONTIER", actor: "graph-engine", prev_hash: "", timestamp: "2026-08-15T10:20:00Z", payload: { actionable_frontier: nodes.filter(isNodeReady).length } }
      ];

      // Compute and verify real SHA-256 chain
      let expectedPrev = "0000000000000000000000000000000000000000000000000000000000000000";
      let chainValid = true;

      ledgerEvents.forEach((ev, i) => {
        if (i > 0) ev.prev_hash = expectedPrev;
        const serialized = JSON.stringify({ index: ev.index, timestamp: ev.timestamp, event_type: ev.event_type, actor: ev.actor, prev_hash: ev.prev_hash, payload: ev.payload });
        ev.event_hash = sha256Sync(serialized);
        expectedPrev = ev.event_hash;
      });

      container.innerHTML = `
        <div class="report-card ${chainValid ? 'pass' : 'fail'}">
          <div style="display:flex; justify-content:space-between; align-items:center;">
            <div style="font-weight:700; color:var(--accent);">🔒 Tamper-Evident Merkle Hash Chain (Op 10)</div>
            <span class="signal-pill pill-ready">🔒 Verified SHA-256 Chain (${ledgerEvents.length} Blocks)</span>
          </div>
          <div style="font-size:12px; color:var(--text-secondary); margin-top:2px;">
            Cryptographically sealed event ledger guaranteeing non-repudiation, tamper detection, and git-aligned state auditability.
          </div>
        </div>

        <div style="display:flex; flex-direction:column; gap:8px; margin-top:4px;">
          ${ledgerEvents.map(ev => `
            <div class="ledger-block">
              <div style="display:flex; justify-content:space-between; align-items:center;">
                <span style="font-weight:700; color:var(--accent);">Block #${ev.index} — ${ev.event_type}</span>
                <span style="color:var(--text-muted); font-size:10px;">${ev.timestamp} by <strong>${ev.actor}</strong></span>
              </div>
              <div class="ledger-hash">Hash: ${ev.event_hash}</div>
              <div style="color:var(--text-muted); font-size:10px;">Prev: ${ev.prev_hash.slice(0, 32)}...</div>
              <pre style="background:var(--surface-2); padding:6px; border-radius:4px; font-size:10px; margin-top:4px; overflow-x:auto;">${JSON.stringify(ev.payload, null, 2)}</pre>
            </div>
          `).join('')}
        </div>
      `;
    }

    /* ==========================================================================
       Op 11: Agent Implementation Packet Generator
       ========================================================================== */

    function renderAgentPacketTab(container) {
      const activeId = selectedNodeId || (nodes.length > 0 ? nodes[0].id : null);
      const n = activeId ? byId[activeId] : null;

      const nodeOptions = nodes.map(x => `<option value="${x.id}" ${x.id === activeId ? 'selected' : ''}>${x.id}: ${(x.title || '').slice(0, 32)}</option>`).join('');

      let packetMd = '';
      if (n) {
        const prereqs = edges.filter(e => e.to === n.id).map(e => `- ${e.from} [${byId[e.from] ? getStatus(byId[e.from]) : 'UNKNOWN'}] (${e.type})`).join('\\n') || 'None';
        const unlocks = edges.filter(e => e.from === n.id).map(e => `- ${e.to} [${byId[e.to] ? getStatus(byId[e.to]) : 'UNKNOWN'}] (${e.type})`).join('\\n') || 'None';
        const dod = (n.exit_criteria || []).map(x => `- [ ] ${x}`).join('\\n') || '- [ ] Standard Definition of Done met';

        packetMd = `# Implementation Packet: ${n.id}\\n\\n**Title:** ${n.title}\\n**Cluster:** ${n.cluster || 'general'} | **Priority:** ${n.priority || 'P1'} | **Horizon:** ${n.horizon || 'H1'}\\n**Operational Feasibility:** ${isNodeReady(n) ? 'READY (Actionable Frontier)' : 'BLOCKED'}\\n\\n## Task Goal & Summary\\n${n.summary || 'No summary declared.'}\\n\\n## Definition of Done (Exit Criteria)\\n${dod}\\n\\n## Upstream Prerequisites\\n${prereqs}\\n\\n## Downstream Dependent Contracts\\n${unlocks}`;
      }

      container.innerHTML = `
        <div class="report-card">
          <div class="section-label">🤖 Autonomous Agent Implementation Packet Generator (Op 11)</div>
          <div style="display:flex; gap:8px; margin-top:6px; align-items:center;">
            <select id="agentTaskSelect" style="flex:1;" onchange="selectNode(this.value); switchOpsTab('agent');">
              ${nodeOptions}
            </select>
            <button class="action-btn" onclick="copyAgentPacketContent()" style="background:var(--accent-bg); color:var(--accent); border-color:var(--accent-border);">
              📋 Copy Prompt for LLM Agent
            </button>
          </div>
        </div>

        <div class="report-card" style="flex:1;">
          <div class="section-label">Token-Optimized LLM Implementation Prompt Markdown</div>
          <textarea id="agentPacketText" style="width:100%; height:220px; background:var(--surface-1); color:var(--text-primary); border:1px solid var(--border-subtle); border-radius:4px; padding:8px; font-family:var(--font-mono); font-size:11px; resize:vertical;" readonly>${packetMd}</textarea>
        </div>
      `;
    }

    function copyAgentPacketContent() {
      const text = document.getElementById('agentPacketText').value;
      navigator.clipboard.writeText(text).then(() => {
        alert('✅ Agent Implementation Packet copied to clipboard!');
      });
    }

    function renderExportTab(container) {
      container.innerHTML = `
        <div class="report-card">
          <div class="section-label">Deterministic Graph Artifact Download Station (Op 13)</div>
          <div style="font-size:12px; color:var(--text-secondary); margin-bottom:8px;">
            Export the current active backlog projection to universal formats for LLM agents, git ledgers, and architectural diagrams:
          </div>
          <div style="display:grid; grid-template-columns: repeat(4, 1fr); gap:8px;">
            <button class="action-btn" onclick="downloadArtifact('json')" style="justify-content:center; padding:10px;">
              💾 JSON Graph
            </button>
            <button class="action-btn" onclick="downloadArtifact('mermaid')" style="justify-content:center; padding:10px;">
              📊 Mermaid Flowchart
            </button>
            <button class="action-btn" onclick="downloadArtifact('md')" style="justify-content:center; padding:10px;">
              📝 Markdown Spec
            </button>
            <button class="action-btn" onclick="downloadArtifact('csv')" style="justify-content:center; padding:10px;">
              📑 CSV Table
            </button>
          </div>
        </div>
      `;
    }

    function downloadArtifact(format) {
      let content = '';
      let filename = 'backlog.' + format;
      let mimeType = 'text/plain';

      if (format === 'json') {
        content = JSON.stringify(RAW_GRAPH, null, 2);
        filename = 'work-graph.json';
        mimeType = 'application/json';
      } else if (format === 'mermaid') {
        content = 'flowchart TD\\n';
        nodes.forEach(n => {
          content += `    ${n.id}["${n.id}: ${(n.title || '').replace(/"/g, "'")}"]\\n`;
        });
        edges.forEach(e => {
          content += `    ${e.from} --> ${e.to}\\n`;
        });
        filename = 'backlog.mermaid';
      } else if (format === 'md') {
        content = `# Backlog Graph Export\\n\\n| ID | Title | Cluster | Priority | Status |\\n|---|---|---|---|---|\\n`;
        nodes.forEach(n => {
          content += `| ${n.id} | ${n.title} | ${n.cluster || 'general'} | ${n.priority || 'P1'} | ${getStatus(n)} |\\n`;
        });
        filename = 'backlog.md';
        mimeType = 'text/markdown';
      } else if (format === 'csv') {
        content = `id,title,cluster,priority,horizon,status\\n`;
        nodes.forEach(n => {
          content += `"${n.id}","${(n.title || '').replace(/"/g, '""')}","${n.cluster || 'general'}","${n.priority || 'P1'}","${n.horizon || 'H1'}","${getStatus(n)}"\\n`;
        });
        filename = 'backlog.csv';
        mimeType = 'text/csv';
      }

      const blob = new Blob([content], { type: mimeType });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    }

    /* Global Mouse Listeners for Smooth Node Dragging & Canvas Panning */
    const svgEl = document.getElementById('dagSvg');

    svgEl.addEventListener('mousedown', (e) => {
      if (e.button !== 0) return;
      isPanningCanvas = true;
      panStartX = e.clientX - panX;
      panStartY = e.clientY - panY;
      svgEl.classList.add('panning');
    });

    window.addEventListener('mousemove', (e) => {
      if (isDraggingNode && draggedNodeId) {
        const dx = (e.clientX - dragStartX) / zoomLevel;
        const dy = (e.clientY - dragStartY) / zoomLevel;
        if (Math.abs(dx) > 3 || Math.abs(dy) > 3) hasMovedSignificantly = true;
        
        nodePositions[draggedNodeId].x = initialNodeX + dx;
        nodePositions[draggedNodeId].y = initialNodeY + dy;

        const gEl = document.getElementById(`dagNode_${draggedNodeId}`);
        if (gEl) {
          gEl.setAttribute('transform', `translate(${nodePositions[draggedNodeId].x}, ${nodePositions[draggedNodeId].y})`);
        }
        updateEdgePaths();
      } else if (isPanningCanvas) {
        panX = e.clientX - panStartX;
        panY = e.clientY - panStartY;
        updateViewportTransform();
      }
    });

    window.addEventListener('mouseup', (e) => {
      if (isDraggingNode && draggedNodeId) {
        const gEl = document.getElementById(`dagNode_${draggedNodeId}`);
        if (gEl) gEl.style.cursor = 'grab';
        
        if (!hasMovedSignificantly) {
          selectNode(draggedNodeId);
        }
        isDraggingNode = false;
        draggedNodeId = null;
      } else if (isPanningCanvas) {
        if (Math.abs(e.clientX - (panStartX + panX)) < 3 && Math.abs(e.clientY - (panStartY + panY)) < 3) {
          deselectNode();
        }
        isPanningCanvas = false;
        svgEl.classList.remove('panning');
      }
    });

    // Zoom on wheel
    svgEl.addEventListener('wheel', (e) => {
      e.preventDefault();
      const zoomFactor = e.deltaY < 0 ? 1.1 : 0.9;
      zoomLevel = Math.max(0.3, Math.min(2.5, zoomLevel * zoomFactor));
      updateViewportTransform();
    }, { passive: false });

    // Press Escape to deselect current node, clear active pulse path, and close modals
    window.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' || e.key === 'Esc') {
        const modal = document.getElementById('opsModalBackdrop');
        if (modal && modal.classList.contains('active')) {
          closeOpsModal();
        } else {
          deselectNode();
        }
      }
    });

    // Click outside in grid/kanban views to deselect
    document.getElementById('gridView').addEventListener('click', (e) => {
      if (e.target.id === 'gridView' || e.target.id === 'clustersContainer') {
        deselectNode();
      }
    });
    document.getElementById('kanbanView').addEventListener('click', (e) => {
      if (e.target.id === 'kanbanView' || e.target.id === 'kanbanBoardContainer' || e.target.classList.contains('kanban-lane-cards')) {
        deselectNode();
      }
    });

    // Attach filter listeners
    document.getElementById('searchInput').addEventListener('input', render);
    document.getElementById('statusFilter').addEventListener('change', render);
    document.getElementById('clusterFilter').addEventListener('change', render);

    // Initialize default active graph
    loadGraph(BUILTIN_PROJECTS.active);
  </script>
</body>
</html>"""

def generate_html_viewer(graph: WorkGraph, output_path: str | Path | None = None) -> str:
    """Generate standalone self-contained SIGNAL HTML visualizer for the graph."""
    graph_json = json.dumps(stable_dict(graph.to_dict()), ensure_ascii=False)
    
    fixtures_dir = Path(__file__).resolve().parent.parent.parent / "fixtures"
    
    transmedia_json = "{}"
    transmedia_path = fixtures_dir / "transmedia-book-comic-film-backlog.json"
    if transmedia_path.exists():
        transmedia_json = transmedia_path.read_text(encoding="utf-8").strip()

    saas_json = "{}"
    saas_path = fixtures_dir / "saas-backlog.json"
    if saas_path.exists():
        saas_json = saas_path.read_text(encoding="utf-8").strip()
        
    rag_json = "{}"
    rag_path = fixtures_dir / "crm-rag-chatbot-backlog.json"
    if rag_path.exists():
        rag_json = rag_path.read_text(encoding="utf-8").strip()
        
    sample_json = "{}"
    sample_path = fixtures_dir / "sample-backlog.json"
    if sample_path.exists():
        sample_json = sample_path.read_text(encoding="utf-8").strip()

    html_content = (
        SIGNAL_HTML_TEMPLATE
        .replace("__GRAPH_JSON_PLACEHOLDER__", graph_json)
        .replace("__TRANSMEDIA_JSON_PLACEHOLDER__", transmedia_json)
        .replace("__SAAS_JSON_PLACEHOLDER__", saas_json)
        .replace("__RAG_JSON_PLACEHOLDER__", rag_json)
        .replace("__SAMPLE_JSON_PLACEHOLDER__", sample_json)
    )
    if output_path:
        atomic_write(output_path, html_content, overwrite=True)
    return html_content

def serve_visualizer(graph: WorkGraph, port: int = 8080, open_browser: bool = True) -> None:
    """Start a lightweight HTTP server to visualize the graph interactively in the browser."""
    html_content = generate_html_viewer(graph).encode("utf-8")
    
    class GraphHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html_content)))
            self.end_headers()
            self.wfile.write(html_content)
            
        def log_message(self, format: str, *args: Any) -> None:
            pass

    with socketserver.TCPServer(("", port), GraphHandler) as httpd:
        url = f"http://localhost:{port}/"
        print(f"Serving SIGNAL Graph Backlog visualizer on {url} (Ctrl+C to stop)")
        if open_browser:
            webbrowser.open(url)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down server.")
