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
    
    /* Grid / Cluster View */
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

    .task-card.chain-downstream {
      border-color: rgba(69, 224, 196, 0.7) !important;
      background: rgba(69, 224, 196, 0.06) !important;
      box-shadow: 0 0 0 1px rgba(69, 224, 196, 0.3);
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
    
    .edge-pulse-downstream {
      stroke: var(--stream) !important;
      stroke-width: 2px !important;
      stroke-dasharray: 8 4;
      animation: electricPulse 0.75s linear infinite;
      filter: drop-shadow(0 0 4px rgba(69, 224, 196, 0.85));
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
      <div class="brand-pill">SIGNAL Graph Backlog</div>
    </div>
    
    <div class="view-tabs">
      <button class="tab-btn active" id="tabGridBtn" onclick="switchView('grid')">Kanban / Clusters</button>
      <button class="tab-btn" id="tabDagBtn" onclick="switchView('dag')">Interactive DAG Canvas</button>
    </div>

    <div class="controls">
      <input type="text" id="searchInput" placeholder="Search tasks, IDs, tags..." style="width: 200px;">
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
      <button class="action-btn" id="resetBtn" onclick="resetFilters()">Reset</button>
    </div>
  </header>

  <div class="main-workspace">
    <!-- Grid / Kanban View -->
    <div class="view-content active" id="gridView">
      <div class="clusters-grid" id="clustersContainer"></div>
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
        <div class="section-label">Simulation (What-If)</div>
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
        <div class="section-label">Upstream Blockers (Prerequisites)</div>
        <div id="inspPrereqs" style="display:flex; flex-direction:column; gap:4px;">None</div>
      </div>

      <div class="section-block">
        <div class="section-label">Downstream Impact (Unlocks)</div>
        <div id="inspDownstream" style="display:flex; flex-direction:column; gap:4px;">None</div>
      </div>

      <button class="action-btn" id="copyPacketBtn" onclick="copyImplementationPacket()" style="justify-content:center; margin-top:8px;">
        📋 Copy Agent Implementation Packet
      </button>
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
    const RAW_GRAPH = __GRAPH_JSON_PLACEHOLDER__;
    const nodes = RAW_GRAPH.nodes || [];
    const edges = RAW_GRAPH.edges || [];
    const byId = {};
    nodes.forEach(n => byId[n.id] = n);

    let selectedNodeId = null;
    let simulatedDoneSet = new Set();
    let showCriticalPath = false;
    let currentView = 'grid';

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

    // Populate cluster filter
    const clusters = [...new Set(nodes.map(n => n.cluster || 'general'))].sort();
    const clusterSelect = document.getElementById('clusterFilter');
    clusters.forEach(c => {
      const opt = document.createElement('option');
      opt.value = c;
      opt.textContent = c;
      clusterSelect.appendChild(opt);
    });

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
       Recursive Dependency & Ancestor Chain Traversals
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

    function switchView(viewName) {
      currentView = viewName;
      document.getElementById('tabGridBtn').className = `tab-btn ${viewName === 'grid' ? 'active' : ''}`;
      document.getElementById('tabDagBtn').className = `tab-btn ${viewName === 'dag' ? 'active' : ''}`;
      document.getElementById('gridView').className = `view-content ${viewName === 'grid' ? 'active' : ''}`;
      document.getElementById('dagView').className = `view-content ${viewName === 'dag' ? 'active' : ''}`;
      if (viewName === 'dag') renderDag();
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

      // Compute active dependency chain sets
      const upstream = getRecursiveUpstream(selectedNodeId);
      const downstream = getRecursiveDownstream(selectedNodeId);

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
            pillClass = 'pill-blocked';
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

          // Chain highlight & dimming (Recursive upstream only)
          let chainClass = '';
          if (selectedNodeId) {
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

          card.innerHTML = `
            <div class="card-top">
              <span class="card-id">${n.id}</span>
              <div class="card-badges">
                <span class="signal-pill ${pillClass}">${pillLabel}</span>
                <span class="signal-pill">${n.priority || 'P1'}</span>
              </div>
            </div>
            <div class="card-title">${n.title || ''}</div>
          `;
          col.appendChild(card);
        });

        container.appendChild(col);
      });

      if (currentView === 'dag') renderDag();
    }

    function selectNode(id) {
      selectedNodeId = id;
      const n = byId[id];
      if (!n) {
        deselectNode();
        return;
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

    function toggleCriticalPath() {
      showCriticalPath = !showCriticalPath;
      document.getElementById('criticalPathBtn').className = `action-btn ${showCriticalPath ? 'active' : ''}`;
      if (currentView === 'dag') renderDag();
    }

    function resetFilters() {
      document.getElementById('searchInput').value = '';
      document.getElementById('statusFilter').value = 'ALL';
      document.getElementById('clusterFilter').value = 'ALL';
      simulatedDoneSet.clear();
      showCriticalPath = false;
      document.getElementById('criticalPathBtn').className = 'action-btn';
      deselectNode();
    }

    function copyImplementationPacket() {
      if (!selectedNodeId) return;
      const n = byId[selectedNodeId];
      const packetMd = `# Implementation Packet: ${n.id}\\n\\n**Title:** ${n.title}\\n**Status:** ${getStatus(n)}\\n\\n## Summary\\n${n.summary || ''}\\n\\n## Definition of Done\\n${(n.exit_criteria || []).map(x => '- [ ] ' + x).join('\\n')}`;
      navigator.clipboard.writeText(packetMd).then(() => {
        const btn = document.getElementById('copyPacketBtn');
        btn.textContent = '✅ Copied to Clipboard!';
        setTimeout(() => btn.textContent = '📋 Copy Agent Implementation Packet', 2000);
      });
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
      const downstream = getRecursiveDownstream(selectedNodeId);

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
          if (selectedNodeId) {
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

        // Dimming & selection classes (Recursive upstream only)
        if (selectedNodeId) {
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
        let strokeColor = '#2B3020';
        if (st === 'DONE') strokeColor = '#8B9173';
        else if (ready) strokeColor = '#CBF23F';
        if (n.id === selectedNodeId) strokeColor = '#CBF23F';
        else if (upstream.nodes.has(n.id)) strokeColor = '#CBF23F';

        const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
        rect.setAttribute('width', '160');
        rect.setAttribute('height', '48');
        rect.setAttribute('rx', '6');
        rect.setAttribute('fill', n.id === selectedNodeId ? '#1B1F14' : '#14170E');
        rect.setAttribute('stroke', strokeColor);
        rect.setAttribute('stroke-width', n.id === selectedNodeId ? '2.5' : (upstream.nodes.has(n.id) ? '2' : '1'));
        
        if (n.id === selectedNodeId) {
          rect.setAttribute('filter', 'drop-shadow(0 0 8px rgba(203, 242, 63, 0.45))');
        } else if (upstream.nodes.has(n.id)) {
          rect.setAttribute('filter', 'drop-shadow(0 0 5px rgba(203, 242, 63, 0.3))');
        }

        g.appendChild(rect);

        // Status indicator pip
        const pip = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        pip.setAttribute('cx', '12');
        pip.setAttribute('cy', '16');
        pip.setAttribute('r', '3.5');
        pip.setAttribute('fill', strokeColor);
        g.appendChild(pip);

        const idText = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        idText.setAttribute('x', '22');
        idText.setAttribute('y', '19');
        idText.setAttribute('fill', '#EDEEE1');
        idText.setAttribute('font-size', '11');
        idText.setAttribute('font-weight', 'bold');
        idText.setAttribute('font-family', '"IBM Plex Mono", ui-monospace, monospace');
        idText.textContent = n.id;
        g.appendChild(idText);

        const titleText = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        titleText.setAttribute('x', '10');
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
        // If clicking on empty canvas without panning, deselect node
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

    // Press Escape to deselect current node and clear active pulse path
    window.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' || e.key === 'Esc') {
        deselectNode();
      }
    });

    // Click outside in grid view to deselect
    document.getElementById('gridView').addEventListener('click', (e) => {
      if (e.target.id === 'gridView' || e.target.id === 'clustersContainer') {
        deselectNode();
      }
    });

    // Attach filter listeners
    document.getElementById('searchInput').addEventListener('input', render);
    document.getElementById('statusFilter').addEventListener('change', render);
    document.getElementById('clusterFilter').addEventListener('change', render);

    render();
  </script>
</body>
</html>"""

def generate_html_viewer(graph: WorkGraph, output_path: str | Path | None = None) -> str:
    """Generate standalone self-contained SIGNAL HTML visualizer for the graph."""
    graph_json = json.dumps(stable_dict(graph.to_dict()), ensure_ascii=False)
    html_content = SIGNAL_HTML_TEMPLATE.replace("__GRAPH_JSON_PLACEHOLDER__", graph_json)
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
