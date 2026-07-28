import os

css = """
/* Tabbed Workspace Styles */
.workspace-tabs {
  display: flex;
  gap: 8px;
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
}

.tab-btn {
  background: transparent;
  border: none;
  color: var(--text-3);
  padding: 8px 16px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 6px;
  transition: all 0.2s ease;
}

.tab-btn:hover {
  color: var(--text-2);
  background: rgba(255, 255, 255, 0.05);
}

.tab-btn.active {
  color: var(--accent-light);
  background: var(--surface-active);
  border: 1px solid var(--border-active);
}

.tab-content-area {
  height: calc(100vh - 56px);
  overflow: hidden;
  background: var(--bg);
}

.tab-pane {
  display: grid;
  height: 100%;
  animation: fade-in 0.3s ease;
}

.brief-pane {
  grid-template-columns: var(--sidebar-w) 1fr;
}

.content-pane {
  grid-template-columns: var(--sidebar-w) 1fr var(--preview-w);
}

.visuals-pane {
  grid-template-columns: var(--sidebar-w) 1fr;
}

.brief-sidebar, .pipeline-sidebar {
  border-right: 1px solid var(--border);
  padding: 24px 20px;
  display: flex;
  flex-direction: column;
  gap: 24px;
  overflow-y: auto;
  background: rgba(3, 3, 7, 0.4);
}

.brief-main, .visuals-main {
  padding: 32px;
  overflow-y: auto;
}

.content-streams {
  padding: 32px;
  overflow-y: auto;
  border-right: 1px solid var(--border);
}

.content-preview {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--surface);
}

.tabbed-workspace {
  display: block; /* Overwrite old grid */
}

@keyframes fade-in {
  from { opacity: 0; transform: translateY(4px); }
  to { opacity: 1; transform: translateY(0); }
}
"""

with open("app/globals.css", "a", encoding="utf-8") as f:
    f.write(css)
