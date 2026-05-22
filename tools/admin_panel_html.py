# -*- coding: utf-8 -*-
"""Admin panel markup embedded for deployment without a separate HTML file."""

ADMIN_HTML = r"""
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Codex凭证管理 · 后台</title>
  <style>
    :root {
      --bg-a: #e8edff;
      --bg-b: #f6f8ff;
      --surface: rgba(255,255,255,0.96);
      --text: #141b2d;
      --muted: #647089;
      --line: rgba(152, 168, 205, 0.34);
      --shadow: 0 18px 44px rgba(72, 88, 130, 0.11);
      --blue: #4f46e5;
      --teal: #0f9f8f;
      --green: #15a36f;
      --red: #ef5a72;
      --amber: #d97706;
      --radius-lg: 20px;
      --radius-md: 14px;
      --control-h: 42px;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "PingFang SC", "Segoe UI", sans-serif;
      color: var(--text);
      background: linear-gradient(180deg, var(--bg-a), var(--bg-b));
      min-height: 100vh;
    }
    .shell { width: min(1240px, calc(100vw - 32px)); margin: 20px auto 36px; display: grid; gap: 16px; }
    .panel {
      border: 1px solid var(--line);
      border-radius: var(--radius-lg);
      background: var(--surface);
      box-shadow: var(--shadow);
      padding: 24px;
    }
    h1 { margin: 0 0 10px; font-size: 32px; letter-spacing: -0.02em; }
    h3 { margin: 0 0 8px; font-size: 18px; letter-spacing: -0.01em; }
    .sub { color: var(--muted); margin-bottom: 18px; line-height: 1.55; font-size: 13px; }
    .hero-top {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 16px;
      margin-bottom: 12px;
    }
    .hero-top h1 { margin: 0; }
    .hero-actions {
      display: flex;
      gap: 10px;
      flex-shrink: 0;
      align-items: center;
    }
    .stats {
      display: grid;
      grid-template-columns: repeat(8, minmax(0, 1fr));
      gap: 12px;
      width: 100%;
    }
    .stat-card {
      padding: 14px 16px;
      border-radius: 16px;
      border: 1px solid var(--line);
      background: linear-gradient(180deg, #ffffff, #f8faff);
      display: grid;
      gap: 6px;
      min-height: 78px;
      align-content: center;
    }
    .stat-label {
      font-size: 12px;
      font-weight: 700;
      color: var(--muted);
      letter-spacing: 0.02em;
    }
    .stat-value {
      font-size: 24px;
      font-weight: 800;
      color: var(--text);
      line-height: 1.1;
    }
    .chip {
      padding: 8px 14px;
      border-radius: 999px;
      border: 1px solid var(--line);
      background: #fff;
      font-weight: 700;
      color: #4b5875;
    }
    .nav-tabs {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      padding: 8px;
      border-radius: 20px;
      background: rgba(255,255,255,0.92);
      border: 1px solid var(--line);
    }
    .nav-tab {
      min-height: 46px;
      padding: 0 22px;
      border-radius: 14px;
      border: 1px solid transparent;
      background: transparent;
      color: #5b6783;
      font-weight: 800;
      cursor: pointer;
    }
    .nav-tab.active {
      color: #fff;
      background: linear-gradient(135deg, var(--blue), var(--teal));
      box-shadow: 0 12px 28px rgba(79, 70, 229, 0.22);
    }
    .tab-panel { display: none; gap: 18px; }
    .tab-panel.active { display: grid; }
    textarea, input, select {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: var(--radius-md);
      padding: 0 14px;
      min-height: var(--control-h);
      font: inherit;
      background: #fff;
      transition: border-color 0.15s ease, box-shadow 0.15s ease;
    }
    textarea:focus, input:focus, select:focus {
      outline: none;
      border-color: rgba(79, 70, 229, 0.45);
      box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.12);
    }
    textarea {
      padding: 12px 14px;
      min-height: 168px;
      font-family: ui-monospace, Consolas, monospace;
      font-size: 12px;
      line-height: 1.55;
      resize: vertical;
    }
    .controls { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin-top: 12px; }
    .button {
      min-height: 44px;
      padding: 0 18px;
      border-radius: 14px;
      border: 1px solid var(--line);
      background: #fff;
      font-weight: 800;
      cursor: pointer;
    }
    .button.primary {
      color: #fff;
      border-color: transparent;
      background: linear-gradient(135deg, var(--blue), var(--teal));
    }
    .button.danger { color: var(--red); }
    .button.small {
      min-height: 34px;
      padding: 0 12px;
      font-size: 13px;
    }
    .button:disabled { opacity: 0.5; cursor: not-allowed; }
    .status { margin-top: 10px; color: var(--muted); font-size: 13px; min-height: 20px; white-space: pre-wrap; }
    .import-progress {
      display: flex;
      align-items: flex-start;
      gap: 10px;
      padding: 12px 14px;
      border-radius: 14px;
      background: rgba(79, 124, 255, 0.08);
      border: 1px solid rgba(79, 124, 255, 0.15);
      color: #35507a;
    }
    .import-progress-main { flex: 1; white-space: pre-wrap; line-height: 1.5; }
    .import-log {
      margin-top: 8px;
      padding: 10px 12px;
      border-radius: 12px;
      background: #101826;
      color: #d7e6ff;
      font-family: ui-monospace, Consolas, monospace;
      font-size: 12px;
      white-space: pre-wrap;
      max-height: 180px;
      overflow: auto;
    }
    .import-spinner {
      width: 16px;
      height: 16px;
      margin-top: 2px;
      border: 2px solid rgba(79, 124, 255, 0.2);
      border-top-color: var(--blue);
      border-radius: 50%;
      animation: import-spin 0.8s linear infinite;
      flex-shrink: 0;
    }
    @keyframes import-spin { to { transform: rotate(360deg); } }
    .login-shell {
      max-width: 460px;
      margin: 72px auto 40px;
      padding: 28px 28px 24px;
      display: grid;
      gap: 22px;
    }
    .login-brand { display: grid; gap: 8px; text-align: center; }
    .login-badge {
      justify-self: center;
      min-height: 28px;
      padding: 0 12px;
      border-radius: 999px;
      background: rgba(79, 70, 229, 0.12);
      color: var(--blue);
      font-size: 12px;
      font-weight: 800;
      display: inline-flex;
      align-items: center;
    }
    .login-brand h1 { margin: 0; font-size: 30px; }
    .login-sub { margin: 0; color: var(--muted); font-size: 14px; line-height: 1.6; }
    .login-form { display: grid; gap: 12px; }
    .login-form label { font-size: 13px; font-weight: 800; color: #4b5875; }
    .remember-row {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      font-size: 13px;
      color: var(--muted);
      user-select: none;
      cursor: pointer;
    }
    .remember-row input { width: 16px; height: 16px; }
    .login-submit { min-height: 44px; font-size: 15px; }
    .inline-actions { display: flex; flex-wrap: wrap; gap: 8px; }
    .api-provider-list {
      margin-top: 18px;
      display: grid;
      gap: 10px;
    }
    .api-provider-card {
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 12px 14px;
      background: rgba(248, 250, 255, 0.92);
      display: grid;
      gap: 6px;
    }
    .api-provider-card strong { font-size: 14px; }
    .api-provider-card .mono { font-size: 12px; color: #334155; word-break: break-all; }
    .about-panel { display: grid; gap: 18px; }
    .about-section {
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 16px 18px;
      background: rgba(248, 250, 255, 0.92);
    }
    .about-section h4 { margin: 0 0 10px; font-size: 16px; }
    .about-section p, .about-section li { margin: 0; color: #4b5875; line-height: 1.7; font-size: 14px; }
    .about-section ul { margin: 0; padding-left: 18px; display: grid; gap: 6px; }
    .about-version-line { margin: 0 0 10px; font-size: 14px; color: #172033; }
    .about-version-line strong { color: var(--blue); }
    .about-changelog { margin: 0; padding-left: 18px; display: grid; gap: 8px; }
    .about-changelog li { color: #4b5875; line-height: 1.65; font-size: 14px; }
    .about-changelog .ver { font-weight: 600; color: #172033; }
    table { width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 13px; }
    th, td { padding: 10px 8px; border-bottom: 1px solid rgba(228,234,246,0.9); text-align: left; vertical-align: middle; }
    .account-email-copy {
      cursor: pointer;
      color: #4f46e5;
      text-decoration: underline dotted;
      text-underline-offset: 2px;
    }
    .account-email-copy:hover { opacity: 0.82; }
    th { color: var(--muted); }
    .col-check { width: 42px; text-align: center; }
    .col-check input[type="checkbox"] { width: 16px; height: 16px; cursor: pointer; }
    tr.data-row { cursor: pointer; transition: background 0.15s ease; }
    tr.data-row.row-selected { background: rgba(79, 70, 229, 0.1); box-shadow: inset 3px 0 0 var(--blue); }
    tr.account-detail-row td { padding: 0; background: rgba(248, 250, 255, 0.92); }
    .mono { font-family: ui-monospace, Consolas, monospace; font-size: 12px; }
    .pill {
      display: inline-flex;
      padding: 4px 10px;
      border-radius: 999px;
      font-weight: 800;
      font-size: 12px;
    }
    .pill.available { background: rgba(21,163,111,0.12); color: var(--green); }
    .pill.used, .pill.assigned { background: rgba(102,116,143,0.12); color: #66748f; }
    .cards-output {
      margin-top: 12px;
      padding: 12px;
      border-radius: 16px;
      background: #101826;
      color: #d7e6ff;
      font-family: ui-monospace, Consolas, monospace;
      font-size: 12px;
      white-space: pre-wrap;
      max-height: 220px;
      overflow: auto;
    }
    .table-head {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      margin-bottom: 4px;
    }
    .table-head h3 { margin: 0; }
    .table-tools {
      display: flex;
      gap: 8px;
      align-items: center;
      flex-wrap: wrap;
    }
    .table-tools label {
      color: var(--muted);
      font-size: 13px;
      font-weight: 700;
    }
    .table-tools select {
      width: auto;
      min-width: 92px;
      padding: 8px 12px;
    }
    .pagination {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 10px;
      margin-top: 12px;
      flex-wrap: wrap;
    }
    .page-info { color: var(--muted); font-size: 13px; }
    .page-actions { display: flex; gap: 8px; align-items: center; }
    .toast {
      position: fixed;
      top: 24px;
      left: 50%;
      transform: translateX(-50%) translateY(-12px);
      min-width: 160px;
      padding: 14px 22px;
      border-radius: 16px;
      background: rgba(23, 32, 51, 0.92);
      color: #f5f8ff;
      font-weight: 800;
      box-shadow: 0 18px 40px rgba(23, 32, 51, 0.24);
      opacity: 0;
      pointer-events: none;
      transition: opacity 0.2s ease, transform 0.2s ease;
      z-index: 10200;
    }
    .toast.show {
      opacity: 1;
      transform: translateX(-50%) translateY(0);
    }
    .toast.success {
      background: rgba(21, 163, 111, 0.96);
      color: #ffffff;
      box-shadow: 0 18px 40px rgba(21, 163, 111, 0.28);
    }
    .toast.error {
      background: rgba(239, 90, 114, 0.96);
      color: #ffffff;
      box-shadow: 0 18px 40px rgba(239, 90, 114, 0.28);
    }
    .modal-backdrop {
      position: fixed;
      inset: 0;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 24px;
      opacity: 0;
      pointer-events: none;
      transition: opacity 0.22s ease;
      z-index: 10000;
      isolation: isolate;
    }
    #version-modal { z-index: 10050; }
    #confirm-modal { z-index: 10060; }
    .modal-backdrop.show {
      opacity: 1;
      pointer-events: auto;
    }
    .modal-scrim {
      position: absolute;
      inset: 0;
      background: rgba(16, 24, 38, 0.52);
      backdrop-filter: blur(8px);
      -webkit-backdrop-filter: blur(8px);
      z-index: 0;
    }
    .modal-dialog {
      position: relative;
      z-index: 1;
      width: min(420px, calc(100vw - 48px));
      max-height: calc(100vh - 48px);
      overflow: auto;
      border-radius: 22px;
      border: 1px solid rgba(152, 168, 205, 0.42);
      background: linear-gradient(180deg, #ffffff 0%, #f8faff 100%);
      box-shadow: 0 28px 64px rgba(36, 52, 92, 0.28);
      padding: 24px 24px 20px;
      transform: translateY(12px) scale(0.98);
      transition: transform 0.22s ease, opacity 0.22s ease;
      opacity: 0;
    }
    .modal-backdrop.show .modal-dialog {
      transform: translateY(0) scale(1);
      opacity: 1;
    }
    .button:disabled,
    .button.primary:disabled {
      opacity: 0.45;
      cursor: not-allowed;
      pointer-events: none;
      filter: grayscale(0.2);
    }
    .modal-head {
      display: flex;
      align-items: flex-start;
      gap: 14px;
      margin-bottom: 18px;
    }
    .modal-icon {
      width: 44px;
      height: 44px;
      border-radius: 14px;
      display: grid;
      place-items: center;
      font-size: 20px;
      font-weight: 900;
      flex-shrink: 0;
      color: #fff;
      background: linear-gradient(135deg, var(--blue), var(--teal));
      box-shadow: 0 10px 24px rgba(79, 70, 229, 0.22);
    }
    .modal-icon.danger {
      background: linear-gradient(135deg, #f05279, var(--red));
      box-shadow: 0 10px 24px rgba(239, 90, 114, 0.24);
    }
    .modal-copy { min-width: 0; }
    .modal-title {
      margin: 0 0 6px;
      font-size: 18px;
      font-weight: 800;
      letter-spacing: -0.01em;
      color: var(--text);
    }
    .modal-message {
      margin: 0;
      color: var(--muted);
      font-size: 14px;
      line-height: 1.6;
      word-break: break-word;
    }
    .modal-actions {
      display: flex;
      justify-content: flex-end;
      gap: 10px;
      margin-top: 4px;
    }
    #version-btn.has-update {
      border-color: rgba(217, 119, 6, 0.45);
      background: rgba(217, 119, 6, 0.12);
      color: #b45309;
    }
    .version-panel {
      display: grid;
      gap: 12px;
      font-size: 14px;
      line-height: 1.55;
      color: #334155;
    }
    .version-row {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      padding: 10px 12px;
      border-radius: 12px;
      background: rgba(241, 245, 255, 0.9);
      border: 1px solid rgba(167, 183, 214, 0.25);
    }
    .version-row strong { color: #172033; }
    .version-note {
      margin: 0;
      white-space: pre-wrap;
      font-size: 13px;
      color: #64748b;
    }
    .version-progress-wrap {
      margin-top: 12px;
      display: grid;
      gap: 6px;
    }
    .version-progress-track {
      height: 8px;
      border-radius: 999px;
      background: rgba(167, 183, 214, 0.35);
      overflow: hidden;
    }
    .version-progress-bar {
      height: 100%;
      width: 0%;
      border-radius: inherit;
      background: linear-gradient(90deg, var(--blue), #22c7b8);
      transition: width 0.35s ease;
    }
    .version-progress-label {
      margin: 0;
      font-size: 13px;
      color: #64748b;
    }
    .version-log {
      margin: 0;
      max-height: 220px;
      overflow: auto;
      padding: 10px 12px;
      border-radius: 12px;
      background: #0f172a;
      color: #e2e8f0;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 12px;
      white-space: pre-wrap;
      line-height: 1.45;
    }
    .button.primary.danger-fill {
      background: linear-gradient(135deg, #f05279, var(--red));
      box-shadow: 0 10px 24px rgba(239, 90, 114, 0.22);
    }
    .field { display: grid; gap: 8px; margin-top: 12px; align-content: start; }
    .settings-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 16px 20px;
      align-items: stretch;
    }
    .settings-grid-wide {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 16px 20px;
      margin-top: 16px;
      align-items: stretch;
    }
    .settings-grid-full {
      display: grid;
      grid-template-columns: 1fr;
      margin-top: 16px;
    }
    .settings-grid-full .field { margin-top: 0; }
    .settings-grid .field-textarea { grid-column: span 1; }
    .settings-grid-wide .field-textarea { grid-column: span 1; }
    .settings-grid .field { margin-top: 0; min-width: 0; }
    .settings-grid .field-textarea textarea { min-height: 168px; height: 168px; }
    .field-label-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
    }
    .field-label-row label { margin: 0; }
    .proxy-test-box {
      margin-top: 4px;
      padding: 12px 14px;
      border-radius: 14px;
      background: #101826;
      color: #d7e6ff;
      font-family: ui-monospace, Consolas, monospace;
      font-size: 12px;
      line-height: 1.6;
      white-space: pre-wrap;
      max-height: 260px;
      overflow: auto;
    }
    .proxy-test-box.ok-line { border: 1px solid rgba(21, 163, 111, 0.35); }
    .proxy-test-box.fail-line { border: 1px solid rgba(239, 90, 114, 0.35); }
    .settings-actions {
      grid-column: 1 / -1;
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      align-items: center;
      margin-top: 4px;
      padding-top: 4px;
    }
    .field label {
      font-size: 13px;
      font-weight: 800;
      color: #4b5875;
    }
    .field-hint {
      color: var(--muted);
      font-size: 12px;
      line-height: 1.5;
    }
    .pill.failed { background: rgba(239, 90, 114, 0.12); color: var(--red); }
    .pill.running { background: rgba(79, 124, 255, 0.12); color: var(--blue); }
    .import-tabs {
      display: flex;
      gap: 8px;
      margin-bottom: 12px;
    }
    .import-tab {
      min-height: 38px;
      padding: 0 16px;
      border-radius: 12px;
      border: 1px solid var(--line);
      background: #fff;
      font-weight: 800;
      cursor: pointer;
      color: #5b6783;
    }
    .import-tab.active {
      color: #fff;
      border-color: transparent;
      background: linear-gradient(135deg, var(--blue), var(--teal));
    }
    .import-toolbar {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 10px 16px;
      margin-bottom: 12px;
    }
    .import-toolbar .import-tabs { margin-bottom: 0; }
    .import-remark-field {
      display: flex;
      align-items: center;
      gap: 8px;
      flex: 1;
      min-width: 200px;
    }
    .import-remark-field label {
      font-size: 13px;
      color: #64748b;
      white-space: nowrap;
    }
    .import-remark-field input {
      flex: 1;
      min-height: var(--control-h);
      padding: 8px 12px;
      border-radius: 12px;
      border: 1px solid var(--line);
      font-size: 13px;
    }
    .account-remark-row {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 8px 12px;
      border-radius: 12px;
      background: rgba(241, 245, 255, 0.9);
      border: 1px solid rgba(167, 183, 214, 0.35);
    }
    .account-remark-label {
      font-size: 13px;
      color: #64748b;
      white-space: nowrap;
    }
    .account-remark-text {
      flex: 1;
      font-size: 14px;
      color: #172033;
      min-height: 20px;
      cursor: text;
      word-break: break-word;
    }
    .account-remark-text.is-empty {
      color: #94a3b8;
      font-style: italic;
    }
    .account-remark-input {
      flex: 1;
      min-height: 36px;
      padding: 6px 10px;
      border-radius: 10px;
      border: 1px solid var(--blue);
      font-size: 14px;
    }
    .button.priority-sale-btn.is-on {
      color: #fff;
      border-color: transparent;
      background: linear-gradient(135deg, #f59e0b, #ea580c);
      box-shadow: 0 8px 18px rgba(234, 88, 12, 0.28);
    }
    .test-panel {
      padding: 14px;
      border-radius: 16px;
      border: 1px solid var(--line);
      background: rgba(248, 250, 255, 0.96);
      display: grid;
      gap: 10px;
    }
    .reauth-panel {
      padding: 12px;
      border-radius: 14px;
      border: 1px dashed rgba(239, 90, 114, 0.35);
      background: rgba(255, 247, 248, 0.96);
      display: grid;
      gap: 10px;
    }
    .reauth-panel.optional-oauth {
      border-color: rgba(15, 159, 143, 0.35);
      background: rgba(244, 255, 252, 0.96);
    }
    .reauth-panel.optional-oauth strong {
      color: #0f766e;
    }
    .mailbox-panel {
      padding: 12px;
      border-radius: 14px;
      border: 1px dashed rgba(79, 70, 229, 0.28);
      background: rgba(246, 248, 255, 0.96);
      display: grid;
      gap: 10px;
    }
    .mailbox-panel strong {
      color: #4338ca;
    }
    .mailbox-panel textarea {
      min-height: 88px;
      font-family: ui-monospace, Consolas, monospace;
      font-size: 12px;
    }
    .reauth-panel strong {
      color: #b42318;
    }
    .account-detail-row td {
      background: rgba(248, 250, 255, 0.72);
      padding-top: 0;
    }
    .oauth-method-tabs {
      margin-bottom: 12px;
    }
    .oauth-panel { display: none; gap: 10px; }
    .oauth-panel.active { display: grid; }
    .auth-link-box {
      padding: 12px;
      border-radius: 14px;
      background: #101826;
      color: #d7e6ff;
      font-family: ui-monospace, Consolas, monospace;
      font-size: 12px;
      word-break: break-all;
    }
    .quota-text {
      font-size: 12px;
      color: #4b5875;
      line-height: 1.5;
    }
    .test-grid {
      display: grid;
      grid-template-columns: minmax(130px, 1fr) minmax(90px, 0.85fr) minmax(120px, 1fr) minmax(110px, 0.9fr) auto;
      gap: 12px;
      align-items: end;
    }
    .test-grid .field { margin-top: 0; min-width: 0; }
    .test-grid .field-action .button {
      white-space: nowrap;
      min-height: var(--control-h);
    }
    .test-grid input,
    .test-grid select {
      min-height: var(--control-h);
    }
    .test-result {
      min-height: 72px;
      padding: 12px;
      border-radius: 14px;
      background: #101826;
      color: #d7e6ff;
      font-family: ui-monospace, Consolas, monospace;
      font-size: 12px;
      white-space: pre-wrap;
    }
    .activity-log-list {
      margin: 0;
    }
    .log-toolbar {
      display: grid;
      grid-template-columns: 120px 140px minmax(140px, 1fr) minmax(140px, 1fr) auto auto;
      gap: 10px;
      align-items: center;
      margin-bottom: 12px;
    }
    .log-toolbar input,
    .log-toolbar select {
      min-height: 38px;
      font-size: 13px;
    }
    .log-auto-refresh {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      color: var(--muted);
      font-size: 13px;
      font-weight: 700;
      white-space: nowrap;
    }
    .log-auto-refresh input { width: auto; min-height: auto; }
    .log-meta-bar {
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 10px;
      min-height: 18px;
    }
    .log-empty {
      padding: 28px;
      text-align: center;
      color: var(--muted);
      border: 1px dashed var(--line);
      border-radius: 14px;
      background: rgba(248, 250, 255, 0.8);
      font-family: ui-monospace, Consolas, monospace;
      font-size: 13px;
    }
    .activity-log-box {
      display: block;
      width: 100%;
      min-height: 420px;
      max-height: 70vh;
      margin: 0;
      overflow: auto;
      padding: 14px 16px;
      border: 1px solid rgba(152, 168, 205, 0.35);
      border-radius: 14px;
      background: #0f172a;
      color: #e2e8f0;
      font-family: ui-monospace, "Cascadia Code", Consolas, monospace;
      font-size: 12px;
      line-height: 1.55;
      white-space: pre;
      word-break: normal;
      overflow-wrap: normal;
      tab-size: 2;
    }
    .activity-log-box:empty::before {
      content: "暂无日志";
      color: #64748b;
    }
    .activity-log-box .log-lvl-error { color: #fca5a5; }
    .activity-log-box .log-lvl-warn { color: #fcd34d; }
    .activity-log-box .log-lvl-info { color: #93c5fd; }
    .activity-log-box .log-lvl-debug { color: #94a3b8; }
    .activity-log-box .log-ts { color: #64748b; }
    .activity-log-box .log-cat { color: #5eead4; }
    .activity-log-box .log-act { color: #c4b5fd; }
    .activity-log-box .log-msg { color: #f8fafc; font-weight: 600; }
    .activity-log-box .log-meta { color: #a5b4fc; }
    .activity-log-box .log-detail { color: #cbd5e1; }
    .activity-log-box .log-sep { color: #334155; }
    @media (max-width: 1400px) {
      .stats { grid-template-columns: repeat(4, minmax(0, 1fr)); }
      .settings-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
    }
    @media (max-width: 1080px) {
      .stats { grid-template-columns: repeat(4, minmax(0, 1fr)); }
      .settings-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .log-toolbar { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    }
    @media (max-width: 900px) {
      .test-grid { grid-template-columns: 1fr; }
      .settings-grid { grid-template-columns: 1fr; }
      .settings-grid .field-textarea { grid-column: span 1; }
      .stats { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .log-toolbar { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <div class="shell">
    <section class="panel login-shell" id="login-panel">
      <div class="login-brand">
        <div class="login-badge">ADMIN</div>
        <h1>Codex凭证管理</h1>
        <p class="login-sub">后台登录 — 管理 PP/GO 账号池、卡密分发、运行日志与 API 网关。</p>
      </div>
      <div class="login-form">
        <label for="admin-password">管理员密码</label>
        <input id="admin-password" type="password" placeholder="请输入密码" autocomplete="current-password">
        <label class="remember-row">
          <input type="checkbox" id="remember-password">
          <span>记住密码</span>
        </label>
        <button class="button primary login-submit" id="login-btn" type="button">登录</button>
        <div class="status" id="login-status"></div>
      </div>
    </section>

    <div id="app-panel" style="display:none;">
      <section class="panel">
        <div class="hero-top">
          <h1>Codex凭证管理 · 后台</h1>
          <div class="hero-actions">
            <button class="button" id="version-btn" type="button" title="版本与更新">v—</button>
            <button class="button" id="refresh-btn">刷新统计</button>
            <button class="button danger" id="logout-btn">退出登录</button>
          </div>
        </div>
        <div class="stats" id="stats"></div>
      </section>

      <section class="panel">
        <div class="nav-tabs">
          <button class="nav-tab active" data-tab="accounts-pp">PP账号池</button>
          <button class="nav-tab" data-tab="accounts-go">GO账号池</button>
          <button class="nav-tab" data-tab="cards">卡密管理</button>
          <button class="nav-tab" data-tab="logs">运行日志</button>
          <button class="nav-tab" data-tab="settings">设置</button>
          <button class="nav-tab" data-tab="about">关于</button>
        </div>
      </section>

      <div class="tab-panel active" id="tab-accounts">
        <section class="panel">
          <h3 id="accounts-pool-title">PP 账号池</h3>
          <h4 style="margin:0 0 12px;font-size:14px;color:#66748f;font-weight:600;">添加账号</h4>
          <div class="import-toolbar">
            <div class="import-tabs">
              <button class="import-tab active" data-import-type="email">Outlook 邮箱</button>
              <button class="import-tab" data-import-type="oauth">ChatGPT OAuth</button>
            </div>
            <div class="import-remark-field">
              <label for="import-remark">备注</label>
              <input id="import-remark" type="text" placeholder="选填，导入时写入每个新账号；不填则为空">
            </div>
          </div>

          <div id="email-import-panel">
            <textarea id="account-material" placeholder="格式：email----password----clientId----refreshToken，一行一个账号。&#10;导入后会自动登录并保存 token，后续测试无需重新登录。"></textarea>
            <div class="controls">
              <button class="button primary" id="import-accounts-btn">导入账号池</button>
            </div>
          </div>

          <div id="oauth-import-panel" style="display:none;">
            <div class="import-tabs oauth-method-tabs">
              <button class="import-tab active" data-oauth-method="manual">手动授权</button>
              <button class="import-tab" data-oauth-method="rt">手动输入RT</button>
              <button class="import-tab" data-oauth-method="mobile_rt">手动输入 Mobile RT</button>
              <button class="import-tab" data-oauth-method="codex_json">Codex JSON / AT 批量输入</button>
            </div>

            <div class="oauth-panel active" id="oauth-panel-manual">
              <div class="controls">
                <button class="button primary" id="oauth-generate-link-btn">生成授权链接</button>
                <button class="button" id="oauth-open-link-btn" disabled>打开链接</button>
                <button class="button" id="oauth-copy-link-btn" disabled>复制链接</button>
              </div>
              <div class="auth-link-box" id="oauth-auth-url">尚未生成授权链接</div>
              <textarea id="oauth-auth-input" placeholder="1. 生成授权链接并在浏览器完成登录；2. 将回调 URL 或 code 粘贴到此处；3. 完成授权并导入。"></textarea>
              <div class="controls">
                <button class="button primary" id="oauth-complete-btn">完成授权并导入</button>
              </div>
            </div>

            <div class="oauth-panel" id="oauth-panel-rt">
              <textarea id="oauth-rt-input" placeholder="一行一个 Codex refresh_token，将自动刷新并导入账号池。"></textarea>
              <div class="controls">
                <button class="button primary" id="oauth-import-rt-btn">导入 RT 账号</button>
              </div>
            </div>

            <div class="oauth-panel" id="oauth-panel-mobile_rt">
              <textarea id="oauth-mobile-rt-input" placeholder="一行一个 Mobile refresh_token（client_id: app_LlGpXReQgckcGGUo2JrYvtJK）。"></textarea>
              <div class="controls">
                <button class="button primary" id="oauth-import-mobile-rt-btn">导入 Mobile RT 账号</button>
              </div>
            </div>

            <div class="oauth-panel" id="oauth-panel-codex_json">
              <textarea id="oauth-codex-input" placeholder="支持 ~/.codex/auth.json、sub2api OAuth JSON、或一行一个 Access Token。"></textarea>
              <div class="controls">
                <button class="button primary" id="oauth-import-codex-btn">导入 Codex 账号</button>
              </div>
            </div>
          </div>

          <div class="status" id="import-status" style="display:none;"></div>
        </section>

        <section class="panel">
          <div class="table-head">
            <h3>账号列表</h3>
            <div class="table-tools">
              <div class="import-tabs account-group-tabs">
                <button class="import-tab active" data-account-group="all">全部</button>
                <button class="import-tab" data-account-group="outlook">Outlook</button>
                <button class="import-tab" data-account-group="oauth">OAuth</button>
              </div>
              <label for="accounts-page-size">每页</label>
              <select id="accounts-page-size"></select>
              <button class="button small danger" id="accounts-delete-selected">删除选中</button>
            </div>
          </div>
          <table>
            <thead><tr><th class="col-check"><input type="checkbox" id="accounts-select-all" title="全选当前页"></th><th>邮箱</th><th>类型</th><th>状态</th><th>额度</th><th>测试</th><th>卡密</th><th>导入日期</th><th>分配时间</th><th style="width:72px;">操作</th></tr></thead>
            <tbody id="accounts-table"></tbody>
          </table>
          <div class="pagination">
            <div class="page-info" id="accounts-page-info"></div>
            <div class="page-actions">
              <button class="button small" id="accounts-prev">上一页</button>
              <button class="button small" id="accounts-next">下一页</button>
            </div>
          </div>
        </section>
      </div>

      <div class="tab-panel" id="tab-cards">
        <section class="panel">
          <div class="table-head" style="margin-bottom:12px;">
            <h3 style="margin:0;">添加卡密</h3>
            <div class="import-tabs card-pool-tabs">
              <button class="import-tab active" data-card-pool="pp">PP 卡密</button>
              <button class="import-tab" data-card-pool="go">GO 卡密</button>
            </div>
          </div>
          <div class="sub" id="cards-format-hint">PP 卡密格式：Codex-P + 20 位大小写字母/数字</div>
          <input id="card-count" type="number" min="1" max="500" value="10">
          <div class="controls">
            <button class="button primary" id="create-cards-btn">生成卡密</button>
            <button class="button" id="copy-cards-btn">复制卡密</button>
          </div>
          <div class="cards-output" id="cards-output">生成后会显示在这里</div>
          <div class="status" id="cards-status"></div>
        </section>

        <section class="panel">
          <div class="table-head">
            <h3>卡密列表</h3>
            <div class="table-tools">
              <div class="import-tabs card-pool-tabs">
                <button class="import-tab active" data-card-pool="pp">PP 卡密</button>
                <button class="import-tab" data-card-pool="go">GO 卡密</button>
              </div>
              <label for="cards-page-size">每页</label>
              <select id="cards-page-size"></select>
              <button class="button small danger" id="cards-delete-selected">删除选中</button>
            </div>
          </div>
          <table>
            <thead><tr><th class="col-check"><input type="checkbox" id="cards-select-all" title="全选当前页"></th><th>卡密</th><th>状态</th><th>绑定邮箱</th><th>创建时间</th><th style="width:72px;">操作</th></tr></thead>
            <tbody id="cards-table"></tbody>
          </table>
          <div class="pagination">
            <div class="page-info" id="cards-page-info"></div>
            <div class="page-actions">
              <button class="button small" id="cards-prev">上一页</button>
              <button class="button small" id="cards-next">下一页</button>
            </div>
          </div>
        </section>
      </div>

      <div class="tab-panel" id="tab-logs">
        <section class="panel">
          <div class="table-head">
            <h3>运行日志</h3>
            <div class="table-tools">
              <button class="button" id="refresh-logs-btn">立即刷新</button>
              <button class="button small danger" id="clear-logs-btn" type="button">清理所有日志</button>
            </div>
          </div>
          <div class="sub">终端代码风格展示：导入、登录、额度、测试、取号、导出、OAuth、设置与 detail JSON（敏感字段已脱敏）。</div>
          <div class="log-toolbar">
            <select id="log-level-filter">
              <option value="">全部级别</option>
              <option value="debug">调试</option>
              <option value="info">信息</option>
              <option value="warn">警告</option>
              <option value="error">错误</option>
            </select>
            <select id="log-category-filter">
              <option value="">全部分类</option>
              <option value="import">导入</option>
              <option value="provision">初始化</option>
              <option value="login">登录</option>
              <option value="quota">额度</option>
              <option value="test">测试</option>
              <option value="export">导出</option>
              <option value="redeem">取号</option>
              <option value="card">卡密</option>
              <option value="oauth">OAuth</option>
              <option value="otp">验证码</option>
              <option value="settings">设置</option>
              <option value="admin">后台</option>
              <option value="delete">删除</option>
              <option value="client">前台</option>
              <option value="system">系统</option>
            </select>
            <input id="log-email-filter" placeholder="邮箱筛选">
            <input id="log-action-filter" placeholder="动作筛选，如 provision.test">
            <label class="log-auto-refresh"><input type="checkbox" id="log-auto-refresh" checked>自动刷新</label>
          </div>
          <div class="log-meta-bar" id="log-meta-bar">加载中...</div>
          <pre class="activity-log-box" id="activity-logs" spellcheck="false" aria-label="运行日志代码视图"></pre>
          <div class="pagination">
            <div class="page-info" id="logs-page-info"></div>
            <div class="page-actions">
              <button class="button small" id="logs-prev">上一页</button>
              <button class="button small" id="logs-next">下一页</button>
            </div>
          </div>
        </section>
      </div>

      <div class="tab-panel" id="tab-settings">
        <section class="panel">
          <h3>系统设置</h3>
          <div class="sub">第一排管理登录与自动测试；第二排管理默认模型、默认回复与对外 API。下方可配置代理池和模型列表。</div>
          <div class="settings-grid">
            <div class="field">
              <label for="setting-password">新登录密码</label>
              <input id="setting-password" type="password" placeholder="留空表示不修改">
            </div>
            <div class="field">
              <label for="setting-password-confirm">确认新密码</label>
              <input id="setting-password-confirm" type="password" placeholder="再次输入新密码">
            </div>
            <div class="field">
              <div class="field-label-row">
                <label for="setting-auto-test-interval">自动测试</label>
                <button class="button small" id="auto-test-now-btn" type="button">立即测试</button>
              </div>
              <select id="setting-auto-test-interval">
                <option value="0">关闭</option>
              </select>
              <div class="field-hint" id="auto-test-status">已关闭</div>
            </div>
            <div class="field">
              <label for="setting-default-model">默认测试模型</label>
              <input id="setting-default-model" placeholder="gpt-5.3-codex">
            </div>
            <div class="field">
              <label for="setting-default-message">默认回复</label>
              <input id="setting-default-message" placeholder="hi">
            </div>
            <div class="field">
              <label for="setting-api-key">对外 API 密钥</label>
              <input id="setting-api-key" class="mono" readonly placeholder="保存后显示">
              <div class="inline-actions">
                <button class="button small" id="copy-api-key-btn" type="button">复制密钥</button>
                <button class="button small danger" id="reset-api-key-btn" type="button">重置密钥</button>
              </div>
              <div class="field-hint">当前生效：<span id="setting-api-base" class="mono">-</span></div>
            </div>
          </div>
          <div class="settings-grid settings-grid-full">
            <div class="field">
              <label for="setting-public-base-url">对外访问地址</label>
              <input id="setting-public-base-url" placeholder="留空自动识别，如 https://api.example.com">
              <div class="field-hint">用于「关于」页 API 示例 URL。留空则按当前浏览器访问地址自动识别；若前面有 Nginx/CDN 反代，请填写公网域名。</div>
            </div>
          </div>
          <div class="settings-grid-wide">
            <div class="field field-textarea">
              <div class="field-label-row">
                <label for="setting-proxy">代理池</label>
                <button class="button small" id="test-proxy-btn" type="button">测试代理池</button>
              </div>
              <textarea id="setting-proxy" placeholder="一行一个代理，留空表示直连。例如：&#10;socks5h://user:pass@host:port"></textarea>
              <div class="field-hint">导入新账号时会按代理池顺序自动分配；也可在账号详情里单独切换。当前已配置 <span id="proxy-count">0</span> 条。</div>
              <div class="proxy-test-box" id="proxy-test-result" hidden></div>
            </div>
            <div class="field field-textarea">
              <label for="setting-test-models">测试模型列表</label>
              <textarea id="setting-test-models" placeholder="一行一个模型名，例如：&#10;gpt-5.3-codex&#10;gpt-5.4"></textarea>
              <div class="field-hint">账号详情里的「模型」下拉和导入后自动检测都会使用这里的列表。</div>
            </div>
          </div>
          <div class="settings-actions">
            <button class="button primary" id="save-settings-btn">保存设置</button>
            <button class="button" id="reset-password-btn">恢复默认密码</button>
          </div>
          <div class="status" id="settings-status"></div>
        </section>
      </div>

      <div class="tab-panel" id="tab-about">
        <section class="panel about-panel">
          <h3>关于本系统</h3>
          <div class="sub">Codex凭证管理（Codex Credential Console）— 卡密分发与账号池，面向 ChatGPT / Codex 账号的导入、检测、取号与 Session 导出。</div>

          <div class="about-section">
            <h4>版本与更新</h4>
            <p class="about-version-line">当前版本：<strong id="about-app-version">加载中…</strong>　右上角「v」按钮可检查 GitHub 更新并一键拉取部署。</p>
            <ul class="about-changelog" id="about-changelog">
              <li><span class="ver">v1.0.22</span> — 版本自动对齐：宿主机 / 界面 / GitHub 一致，启动与一键更新自动同步。</li>
              <li><span class="ver">v1.0.19</span> — 一键更新：进度条 + 详细日志；独立容器重建，修复误报「操作失败」。</li>
              <li><span class="ver">v1.0.18</span> — 修复版本检测：只读 GitHub main/VERSION，避免 CDN/旧 Release 误报已是最新。</li>
              <li><span class="ver">v1.0.17</span> — 关于页增加「版本与更新」说明；版本弹窗界面精简。</li>
              <li><span class="ver">v1.0.16</span> — 版本号与更新说明整理。</li>
              <li><span class="ver">v1.0.15</span> — 版本弹窗去掉图标、副标题「仅点击检查更新才访问 GitHub」、数据库路径行。</li>
              <li><span class="ver">v1.0.14</span> — GitHub 最新版取 main/VERSION、Release、标签三者最高版本；Docker 挂载 core/tools 便于热更新。</li>
              <li><span class="ver">v1.0.8</span> — 一键更新（Docker git + 重建）、检查更新才访问 GitHub、Toast 置于弹窗之上。</li>
            </ul>
          </div>

          <div class="about-section">
            <h4>系统能做什么</h4>
            <ul>
              <li><strong>双池管理：</strong>PP 池（Codex-P）与 GO 池（Codex-G）账号、卡密独立统计与分发。</li>
              <li><strong>卡密取号：</strong>前台用户输入卡密后自动分配测试通过的可用账号，并可在浏览器本地登录、读验证码、导出 Session。</li>
              <li><strong>账号导入：</strong>支持 Outlook 四段素材、OAuth 授权、Refresh Token、Mobile RT、Codex JSON / Access Token 等多种方式。</li>
              <li><strong>自动检测：</strong>导入后自动登录、查额度、跑模型测试；后台可设置定时全量自动测试。</li>
              <li><strong>Session 导出：</strong>支持 sub2api、cpa、cockpit、9router、axonhub 等格式。</li>
              <li><strong>对外 API：</strong>提供可重置密钥的网关，按 OpenAI 兼容路径转发到 OpenAI、Codex、OpenRouter、Groq 等上游。</li>
            </ul>
          </div>

          <div class="about-section">
            <h4>后台页面说明</h4>
            <ul>
              <li><strong>PP/GO 账号池：</strong>导入账号、查看状态（可用 / 异常 / 已分配）、额度、测试结果，支持单账号测试、查额度、读邮箱验证码、OAuth 重新授权与导出。</li>
              <li><strong>卡密管理：</strong>批量生成 PP/GO 卡密，查看使用状态，删除后对应账号会回到可用池。</li>
              <li><strong>运行日志：</strong>导入、登录、额度、测试、取号、导出、OAuth、设置等全链路结构化日志，可筛选与清理。</li>
              <li><strong>设置：</strong>修改后台密码、代理池、测试模型、默认回复、自动测试周期，以及重置对外 API 密钥。</li>
            </ul>
          </div>

          <div class="about-section">
            <h4>账号状态规则</h4>
            <ul>
              <li><strong>可用：</strong>未分配、测试通过、额度正常。</li>
              <li><strong>异常：</strong>测试失败或额度刷新失败（如 token 失效），不会参与卡密取号。</li>
              <li><strong>已分配：</strong>卡密已取走，绑定到具体卡密代码。</li>
            </ul>
          </div>

          <div class="about-section">
            <h4>对外 API 调用方式</h4>
            <p>在请求头加入 <span class="mono">Authorization: Bearer &lt;API密钥&gt;</span>。密钥可在「设置」页复制或重置；重置后旧密钥立即失效。</p>
            <p>网关根地址可在「设置 → 对外访问地址」中配置；留空则自动使用当前访问域名（支持 Nginx 反代的 <span class="mono">X-Forwarded-Host</span> 头）。</p>
            <p>当前生效地址：<span class="mono" id="about-api-base">-</span></p>
            <div class="api-provider-list" id="about-api-list"></div>
          </div>

          <div class="about-section">
            <h4>前台用户流程</h4>
            <ul>
              <li>打开首页 → 输入 PP/GO 卡密 → 取号成功后在本地表格看到账号。</li>
              <li>可读取 Outlook 验证码、导出选中 Session 文件；右上角可切换中文 / English。</li>
              <li>取号数据保存在浏览器本地，不会自动同步到其他设备。</li>
            </ul>
          </div>

          <div class="about-section">
            <h4>部署与重启</h4>
            <p>推荐 Docker：<span class="mono">docker compose up -d</span>；日常更新可在右上角版本弹窗点「检查更新」→「一键更新」。</p>
            <p>本机开发：<span class="mono">python tools/session_converter_web.py --host 127.0.0.1 --port 8766</span></p>
            <p>后台地址：<span class="mono">/admin</span>　前台地址：<span class="mono">/</span>　修改界面后请 Ctrl+F5 强刷。</p>
          </div>
        </section>
      </div>
    </div>
  </div>
  <div id="toast" class="toast">已刷新</div>
  <div id="confirm-modal" class="modal-backdrop" aria-hidden="true">
    <div class="modal-scrim" aria-hidden="true"></div>
    <div class="modal-dialog" id="confirm-modal-dialog" role="dialog" aria-modal="true" aria-labelledby="confirm-modal-title">
      <div class="modal-head">
        <div class="modal-icon" id="confirm-modal-icon">?</div>
        <div class="modal-copy">
          <h4 class="modal-title" id="confirm-modal-title">请确认</h4>
          <p class="modal-message" id="confirm-modal-message"></p>
        </div>
      </div>
      <div class="modal-actions">
        <button class="button" type="button" id="confirm-modal-cancel">取消</button>
        <button class="button primary" type="button" id="confirm-modal-confirm">确定</button>
      </div>
    </div>
  </div>
  <div id="version-modal" class="modal-backdrop" aria-hidden="true">
    <div class="modal-scrim" aria-hidden="true"></div>
    <div class="modal-dialog" role="dialog" aria-modal="true" aria-labelledby="version-modal-title">
      <div class="modal-head">
        <div class="modal-copy">
          <h4 class="modal-title" id="version-modal-title">版本与更新</h4>
        </div>
      </div>
      <div class="version-panel" id="version-modal-body">加载中…</div>
      <div class="modal-actions">
        <button class="button" type="button" id="version-modal-close">关闭</button>
      </div>
    </div>
  </div>

  <script>
    const TOKEN_KEY = "gpt-admin-token";
    const REMEMBER_PASSWORD_KEY = "gpt-admin-remember-password";
    const SAVED_PASSWORD_KEY = "gpt-admin-saved-password";
    const ACCOUNT_GROUP_KEY = "gpt-admin-account-group";
    const CARD_POOL_KEY = "gpt-admin-card-pool";
    const CARDS_PAGE_SIZE_KEY = "gpt-admin-cards-page-size";
    const ACCOUNTS_PAGE_SIZE_KEY = "gpt-admin-accounts-page-size";
    const EXPANDED_ACCOUNT_KEY = "gpt-admin-expanded-account";
    const VALID_TABS = ["accounts-pp", "accounts-go", "cards", "logs", "settings", "about"];
    const ACCOUNT_TABS = ["accounts-pp", "accounts-go"];
    const POOL_LABELS = { pp: "PP", go: "GO" };
    let accountPollTimer = null;
    const PAGE_SIZE_OPTIONS = [10, 50, 100, 500, 1000, 5000];
    function readStoredPageSize(key, fallback = 10) {
      const raw = Number(localStorage.getItem(key));
      return PAGE_SIZE_OPTIONS.includes(raw) ? raw : fallback;
    }
    const listState = {
      cards: {
        page: 1,
        pageSize: readStoredPageSize(CARDS_PAGE_SIZE_KEY),
        poolType: localStorage.getItem(CARD_POOL_KEY) || "pp",
      },
      accounts: {
        page: 1,
        pageSize: readStoredPageSize(ACCOUNTS_PAGE_SIZE_KEY),
        group: localStorage.getItem(ACCOUNT_GROUP_KEY) || "all",
        poolType: "pp",
      },
    };
    let toastTimer = null;
    let confirmResolver = null;
    function isAccountsTab(tabName) {
      return ACCOUNT_TABS.includes(tabName);
    }
    function accountTabPoolType(tabName) {
      return tabName === "accounts-go" ? "go" : "pp";
    }
    function currentAccountPoolType() {
      return isAccountsTab(activeTab) ? accountTabPoolType(activeTab) : (listState.accounts.poolType || "pp");
    }
    function statsPoolType() {
      if (isAccountsTab(activeTab)) return accountTabPoolType(activeTab);
      if (activeTab === "cards") return listState.cards.poolType || "pp";
      return "";
    }
    function resolveTabName(tabName) {
      if (tabName === "accounts") return "accounts-pp";
      return VALID_TABS.includes(tabName) ? tabName : "accounts-pp";
    }

    function readTabFromLocation() {
      const hashTab = resolveTabName((location.hash || "").replace(/^#/, "").trim());
      if ((location.hash || "").replace(/^#/, "").trim()) {
        return hashTab;
      }
      const savedTab = sessionStorage.getItem("gpt-admin-active-tab") || "";
      return resolveTabName(savedTab);
    }

    let activeTab = readTabFromLocation();
    let logsPollTimer = null;
    let autoTestPollTimer = null;
    const logState = { page: 1, pageSize: 100 };
    let importAccountType = "email";
    let oauthMethod = "manual";
    let oauthSession = { sessionId: "", state: "", authUrl: "" };
    const EXPORT_FORMATS = [
      { value: "sub2api", label: "sub2api" },
      { value: "cpa", label: "cpa" },
      { value: "cockpit", label: "cockpit" },
      { value: "9router", label: "9router" },
      { value: "axonhub", label: "axonhub" },
      { value: "all", label: "全部" },
    ];
    let testOptions = {
      models: ["gpt-5.4", "gpt-5.4-mini", "gpt-5.5", "gpt-5.3-codex", "gpt-5.2"],
      defaultModel: "gpt-5.3-codex",
      defaultMessage: "hi",
      proxyOptions: [{ value: "", label: "直连（无代理）" }],
    };
    let testingAccount = null;
    let reauthOpenAccountId = "";
    const reauthSessions = {};
    const reauthModes = {};
    let mailboxOpenAccountId = "";
    let mailboxBusyAccountId = "";
    const mailboxOtpByAccount = {};
    let selectedAccountId = "";
    const selectedAccountIds = new Set();
    const selectedCardCodes = new Set();
    let accountRowClickTimer = null;
    const savedExpandedAccountId = sessionStorage.getItem(EXPANDED_ACCOUNT_KEY) || "";
    const $ = (id) => document.getElementById(id);

    function showConfirm({
      title = "请确认",
      message = "",
      confirmText = "确定",
      cancelText = "取消",
      danger = false,
    } = {}) {
      return new Promise((resolve) => {
        if (confirmResolver) {
          confirmResolver(false);
          confirmResolver = null;
        }
        const backdrop = $("confirm-modal");
        const icon = $("confirm-modal-icon");
        const confirmBtn = $("confirm-modal-confirm");
        $("confirm-modal-title").textContent = title;
        $("confirm-modal-message").textContent = message;
        $("confirm-modal-cancel").textContent = cancelText;
        confirmBtn.textContent = confirmText;
        icon.textContent = danger ? "!" : "?";
        icon.classList.toggle("danger", Boolean(danger));
        confirmBtn.classList.toggle("danger-fill", Boolean(danger));
        confirmResolver = resolve;
        backdrop.classList.add("show");
        backdrop.setAttribute("aria-hidden", "false");
        document.body.style.overflow = "hidden";
        setTimeout(() => $("confirm-modal-cancel").focus(), 0);
      });
    }

    function closeConfirm(result) {
      const backdrop = $("confirm-modal");
      backdrop.classList.remove("show");
      backdrop.setAttribute("aria-hidden", "true");
      document.body.style.overflow = "";
      if (confirmResolver) {
        const resolve = confirmResolver;
        confirmResolver = null;
        resolve(Boolean(result));
      }
    }

    $("confirm-modal-cancel").addEventListener("click", () => closeConfirm(false));
    $("confirm-modal-confirm").addEventListener("click", () => closeConfirm(true));
    $("confirm-modal").addEventListener("click", (event) => {
      if (event.target === $("confirm-modal")) closeConfirm(false);
    });
    $("confirm-modal-dialog").addEventListener("click", (event) => event.stopPropagation());
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && $("confirm-modal").classList.contains("show")) {
        event.preventDefault();
        closeConfirm(false);
      }
    });

    const ADMIN_ERROR_ZH_MAP = {
      "cannot rollback - no transaction is active": "系统繁忙，请稍后重试",
      "database is locked": "数据库繁忙，请稍后重试",
      "database disk image is malformed": "数据库异常，请联系管理员",
      "no such table": "数据库结构异常，请重启服务",
      "no such column": "数据库结构异常，请重启服务",
      "unique constraint failed": "数据冲突，请刷新后重试",
      "foreign key constraint failed": "数据关联异常，请刷新后重试",
      "http error 403": "HTTP 403 禁止访问（请确认账号已选代理并点「重新登录」）",
      "http error 401": "HTTP 401 未授权",
      "failed to fetch": "网络请求失败（连接中断或 502）",
    };

    function localizeAdminError(message, fallback = "") {
      const text = String(message || "").trim();
      if (!text) return fallback || "操作失败";
      if (/[\u4e00-\u9fff]/.test(text)) return text;
      const lowered = text.toLowerCase();
      for (const [key, value] of Object.entries(ADMIN_ERROR_ZH_MAP)) {
        if (lowered.includes(key)) return value;
      }
      return text;
    }

    function formatAdminErrorForPanel(error, data = null) {
      const msg = localizeAdminError(error?.message || error, "");
      const detail = data?.detail || data?.error;
      const lines = ["操作失败", `原因: ${msg || "未知"}`];
      if (detail && String(detail).trim() && String(detail).trim() !== msg) {
        lines.push(`详情: ${String(detail).trim()}`);
      }
      return lines.join("\n");
    }

    const LOG_LEVEL_LABELS = { debug: "调试", info: "信息", warn: "警告", error: "错误" };
    const LOG_CATEGORY_LABELS = {
      import: "导入",
      provision: "初始化",
      login: "登录",
      quota: "额度",
      test: "测试",
      export: "导出",
      redeem: "取号",
      card: "卡密",
      oauth: "OAuth",
      otp: "验证码",
      settings: "设置",
      admin: "后台",
      delete: "删除",
      client: "前台",
      system: "系统",
    };

    function formatLogLevelLabel(level) {
      return LOG_LEVEL_LABELS[(level || "info").toLowerCase()] || level || "信息";
    }

    function formatLogCategoryLabel(category) {
      return LOG_CATEGORY_LABELS[(category || "system").toLowerCase()] || category || "系统";
    }

    function showToast(message = "已刷新", type = "success", durationMs = 1500) {
      const toast = $("toast");
      const rawMsg = String(message || "");
      const skipLocalize = /更新|日志|docker|git|compose/i.test(rawMsg);
      toast.textContent = type === "error" && !skipLocalize ? localizeAdminError(rawMsg) : rawMsg;
      toast.classList.remove("success", "error", "show");
      toast.classList.add(type === "error" ? "error" : "success", "show");
      if (toastTimer) clearTimeout(toastTimer);
      toastTimer = setTimeout(() => {
        toast.classList.remove("show", "success", "error");
        toastTimer = null;
      }, durationMs);
    }

    function token() {
      return localStorage.getItem(TOKEN_KEY) || "";
    }

    function setToken(value) {
      if (value) localStorage.setItem(TOKEN_KEY, value);
      else localStorage.removeItem(TOKEN_KEY);
    }

    async function adminFetch(url, options = {}) {
      const headers = {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${token()}`,
        ...(options.headers || {}),
      };
      let res;
      try {
        res = await fetch(url, { ...options, headers });
      } catch (error) {
        const err = new Error(error?.message || "网络请求失败");
        err.apiData = { detail: String(error?.message || error) };
        throw err;
      }
      if (res.status === 401) {
        setToken("");
        showLogin();
        throw new Error("登录已过期，请重新登录");
      }
      return res;
    }

    async function readAdminJson(res, fallbackMessage = "请求失败") {
      const contentType = (res.headers.get("content-type") || "").toLowerCase();
      const raw = await res.text();
      if (contentType.includes("application/json")) {
        try {
          return JSON.parse(raw || "{}");
        } catch (error) {
          throw new Error(`${fallbackMessage}：响应 JSON 解析失败`);
        }
      }
      if (raw.trim().startsWith("<!doctype") || raw.trim().startsWith("<html")) {
        if (res.status === 404) {
          throw new Error("接口不存在，请重启服务后再试（当前运行的可能是旧版本）");
        }
        throw new Error(`${fallbackMessage}：服务器返回了 HTML 而不是 JSON（HTTP ${res.status}）`);
      }
      try {
        return JSON.parse(raw || "{}");
      } catch (error) {
        throw new Error(raw.trim() || `${fallbackMessage}（HTTP ${res.status}）`);
      }
    }

    function showLogin() {
      $("login-panel").style.display = "";
      $("app-panel").style.display = "none";
    }

    function showApp() {
      $("login-panel").style.display = "none";
      $("app-panel").style.display = "";
    }

    function updateAccountsPoolHeading() {
      const title = $("accounts-pool-title");
      if (!title || !isAccountsTab(activeTab)) return;
      title.textContent = `${POOL_LABELS[accountTabPoolType(activeTab)]} 账号池`;
    }

    function updateCardsPoolUi() {
      document.querySelectorAll(".card-pool-tabs [data-card-pool]").forEach((tab) => {
        tab.classList.toggle("active", tab.dataset.cardPool === listState.cards.poolType);
      });
      const hint = $("cards-format-hint");
      if (hint) {
        hint.textContent = listState.cards.poolType === "go"
          ? "GO 卡密格式：Codex-G + 20 位大小写字母/数字"
          : "PP 卡密格式：Codex-P + 20 位大小写字母/数字";
      }
    }

    function switchTab(tabName, { updateHistory = true } = {}) {
      activeTab = resolveTabName(tabName);
      if (isAccountsTab(activeTab)) {
        listState.accounts.poolType = accountTabPoolType(activeTab);
        listState.accounts.page = 1;
      }
      if (updateHistory) {
        const nextHash = `#${activeTab}`;
        if (location.hash !== nextHash) {
          history.replaceState(null, "", nextHash);
        }
        sessionStorage.setItem("gpt-admin-active-tab", activeTab);
      }
      document.querySelectorAll(".nav-tab").forEach((tab) => {
        tab.classList.toggle("active", tab.dataset.tab === activeTab);
      });
      document.querySelectorAll(".tab-panel").forEach((panel) => {
        const showAccounts = panel.id === "tab-accounts" && isAccountsTab(activeTab);
        const showDirect = panel.id === `tab-${activeTab}`;
        panel.classList.toggle("active", showAccounts || showDirect);
      });
      updateAccountsPoolHeading();
      if (activeTab === "cards") updateCardsPoolUi();
      if (isAccountsTab(activeTab)) {
        loadAccounts().catch((error) => showToast(error.message || "加载账号失败", "error"));
        loadStats().catch(() => {});
      } else if (activeTab === "cards") {
        loadCards().catch((error) => showToast(error.message || "加载卡密失败", "error"));
        loadStats().catch(() => {});
      }
      if (activeTab === "logs") {
        startLogsAutoRefresh();
        loadActivityLogs().catch((error) => {
          const box = $("activity-logs");
          if (box) box.textContent = `# ERROR: ${localizeAdminError(error.message, "加载日志失败")}\n`;
        });
      } else {
        stopLogsAutoRefresh();
      }
      if (activeTab === "settings") {
        loadSettings().catch(() => {});
      }
      if (activeTab === "about") {
        loadSettings().catch(() => {});
        loadAboutVersion().catch(() => {});
      }
    }

    function stopLogsAutoRefresh() {
      if (logsPollTimer) {
        clearInterval(logsPollTimer);
        logsPollTimer = null;
      }
    }

    function startLogsAutoRefresh() {
      stopLogsAutoRefresh();
      if (!$("log-auto-refresh")?.checked) return;
      logsPollTimer = setInterval(() => {
        if (activeTab === "logs") {
          loadActivityLogs({ silent: true }).catch(() => {});
        }
      }, 5000);
    }

    function escapeHtml(text) {
      return String(text ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
    }

    function fillPageSizeSelect(selectId, current) {
      const select = $(selectId);
      select.innerHTML = PAGE_SIZE_OPTIONS.map((size) =>
        `<option value="${size}" ${size === current ? "selected" : ""}>${size}</option>`
      ).join("");
    }

    function accountTypeLabel(type) {
      return type === "oauth" ? "OAuth" : "邮箱";
    }

    function groupNameLabel(groupName) {
      const labels = { outlook: "Outlook", oauth: "OAuth" };
      return labels[groupName] || groupName || "-";
    }

    function updateAccountGroupTabs() {
      document.querySelectorAll(".account-group-tabs [data-account-group]").forEach((tab) => {
        tab.classList.toggle("active", tab.dataset.accountGroup === listState.accounts.group);
      });
    }

    function testStatusLabel(status) {
      if (status === "success") return "通过";
      if (status === "failed") return "失败";
      if (status === "running") return "检测中";
      if (status === "pending") return "排队中";
      return "-";
    }

    function testStatusClass(status) {
      if (status === "success") return "available";
      if (status === "failed") return "failed";
      if (status === "running" || status === "pending") return "running";
      return "used";
    }

    function accountIsAbnormal(row) {
      if (!row || row.status === "assigned") return false;
      if (row.testStatus === "failed") return true;
      if (row.quota && row.quota.ok === false) return true;
      const result = row.testResult || {};
      if (result.ok === false || result.error) return true;
      return false;
    }

    function accountPoolStatus(row) {
      if (row.status === "assigned") return { label: "已分配", className: "assigned" };
      if (row.testStatus === "pending" || row.testStatus === "running") return { label: "检测中", className: "running" };
      if (accountIsAbnormal(row)) return { label: "异常", className: "failed" };
      if (row.status === "available" && row.testStatus === "success") return { label: "可用", className: "available" };
      return { label: "待检测", className: "used" };
    }

    function hasPendingAccounts(rows) {
      return (rows || []).some((row) => row.testStatus === "pending" || row.testStatus === "running");
    }

    function scheduleAccountPolling() {
      if (accountPollTimer) return;
      accountPollTimer = setInterval(async () => {
        try {
          await loadAccounts();
          if (!hasPendingAccounts(listState.lastAccounts)) {
            clearInterval(accountPollTimer);
            accountPollTimer = null;
          }
        } catch (error) {
          // 忽略轮询错误
        }
      }, 2500);
    }

    function quotaSummary(row) {
      if (row?.testStatus === "pending" || row?.testStatus === "running") return "检测中";
      const quota = row.quota;
      if (!quota) return "-";
      if (quota.summary) return quota.summary;
      if (quota.error) return "查询失败";
      return "-";
    }

    function resolvePlanType(row) {
      const quota = row?.quota;
      const testQuota = row?.testResult?.quota;
      return (
        row?.planType
        || quota?.planType
        || quota?.raw?.plan_type
        || testQuota?.planType
        || testQuota?.raw?.plan_type
        || ""
      ).trim();
    }

    function formatPlanTypeLabel(planType) {
      const plan = (planType || "").trim().toLowerCase();
      const labels = {
        plus: "Plus",
        free: "Free",
        team: "Team",
        pro: "Pro",
        enterprise: "Enterprise",
        go: "Go",
      };
      return labels[plan] || (planType ? planType : "未查询");
    }

    function resolveQuotaQueryTime(row) {
      return (
        row?.quotaUpdatedAt
        || row?.quota?.queriedAt
        || row?.testResult?.quota?.queriedAt
        || ""
      ).trim();
    }

    function formatActivityLogLine(row) {
      const parts = [
        `[${formatDisplayTime(row.createdAt, "-")}] ${row.email}`,
        `测试: ${testStatusLabel(row.testStatus)}`,
      ];
      if (row.quota?.summary) parts.push(`额度: ${row.quota.summary}`);
      if (row.planType || row.quota?.planType) parts.push(`套餐: ${formatPlanTypeLabel(row.planType || row.quota?.planType || "")}`);
      if (row.testResult?.error) parts.push(`错误: ${localizeAdminError(row.testResult.error, row.testResult.error)}`);
      else if (row.testResult?.reply) parts.push(`回复: ${String(row.testResult.reply).slice(0, 80)}`);
      if (row.lastTestAt) parts.push(`检测: ${formatDisplayTime(row.lastTestAt, "-")}`);
      return parts.join(" | ");
    }

    function renderLogEntryCode(row) {
      const level = String(row.level || "info").toLowerCase();
      const levelLabel = formatLogLevelLabel(level).toUpperCase().padEnd(4, " ");
      const ts = escapeHtml(formatDisplayTime(row.createdAt, "-"));
      const cat = escapeHtml(formatLogCategoryLabel(row.category));
      const act = escapeHtml(row.action || "-");
      const msg = escapeHtml(String(row.message || "-").replace(/\s+/g, " ").trim());
      const metaParts = [];
      if (row.email) metaParts.push(`email=${row.email}`);
      if (row.accountId) metaParts.push(`accountId=${row.accountId}`);
      if (row.cardCode) metaParts.push(`cardCode=${row.cardCode}`);
      if (row.clientId) metaParts.push(`clientId=${row.clientId}`);
      if (row.status) metaParts.push(`status=${row.status}`);
      if (row.durationMs != null) metaParts.push(`durationMs=${row.durationMs}`);
      const metaLine = metaParts.length
        ? `\n<span class="log-meta">  meta: ${escapeHtml(metaParts.join("  "))}</span>`
        : "";
      let detailBlock = "";
      const detail = row.detail;
      if (detail && typeof detail === "object" && Object.keys(detail).length) {
        const json = escapeHtml(JSON.stringify(detail, null, 2));
        detailBlock = `\n<span class="log-detail">  detail:\n${json.split("\n").map((line) => `    ${line}`).join("\n")}</span>`;
      }
      return [
        `<span class="log-ts">[${ts}]</span> `,
        `<span class="log-lvl-${escapeHtml(level)}">${escapeHtml(levelLabel)}</span> `,
        `<span class="log-cat">${cat}</span>`,
        `<span class="log-act">/${act}</span> `,
        `<span class="log-msg">${msg}</span>`,
        metaLine,
        detailBlock,
      ].join("");
    }

    async function loadActivityLogs({ silent = false } = {}) {
      const box = $("activity-logs");
      const meta = $("log-meta-bar");
      if (!box) return;
      if (!silent) {
        box.textContent = "# 加载中...\n";
        if (meta) meta.textContent = "加载中...";
      }
      const params = new URLSearchParams({
        page: String(logState.page),
        pageSize: String(logState.pageSize),
      });
      const level = $("log-level-filter")?.value || "";
      const category = $("log-category-filter")?.value || "";
      const email = $("log-email-filter")?.value?.trim() || "";
      const action = $("log-action-filter")?.value?.trim() || "";
      if (level) params.set("level", level);
      if (category) params.set("category", category);
      if (email) params.set("email", email);
      if (action) params.set("action", action);

      const res = await adminFetch(`/api/admin/logs?${params.toString()}`);
      const data = await readAdminJson(res, "加载日志失败");
      if (!res.ok) throw new Error(data.error || "加载日志失败");
      const rows = data.items || [];
      if (!rows.length) {
        box.textContent = "# 暂无匹配日志\n";
      } else {
        const sep = '<span class="log-sep">────────────────────────────────────────────────────────────────</span>';
        box.innerHTML = rows.map((row) => renderLogEntryCode(row)).join(`\n${sep}\n`);
      }
      if (meta) {
        meta.textContent = `共 ${data.total || 0} 条 · 第 ${data.page || 1}/${data.totalPages || 1} 页 · 每页 ${data.pageSize || logState.pageSize} 条 · 刷新于 ${formatDisplayTime(new Date().toISOString())}`;
      }
      $("logs-page-info").textContent = `第 ${data.page || 1} / ${data.totalPages || 1} 页，共 ${data.total || 0} 条`;
      $("logs-prev").disabled = (data.page || 1) <= 1;
      $("logs-next").disabled = (data.page || 1) >= (data.totalPages || 1);
    }

    function formatDisplayTime(value, emptyLabel = "未查询") {
      if (!value) return emptyLabel;
      const text = String(value).trim();
      if (/^\d{4}-\d{2}-\d{2}T/.test(text)) {
        return text.replace("T", " ").replace(/(\.\d+)?(Z|[+-]\d{2}:\d{2})?$/, "");
      }
      return text;
    }

    function escapeAttr(text) {
      return String(text ?? "")
        .replace(/&/g, "&amp;")
        .replace(/"/g, "&quot;")
        .replace(/</g, "&lt;");
    }

    function buildProxyOptions(row) {
      const current = String(row.assignedProxy ?? "");
      const options = [...(testOptions.proxyOptions || [{ value: "", label: "直连（无代理）" }])];
      const selected = options.some((item) => item.value === current) ? current : "";
      return options.map((item) =>
        `<option value="${escapeAttr(item.value)}" ${item.value === selected ? "selected" : ""}>${escapeHtml(item.label)}</option>`
      ).join("");
    }

    function formatAccountInfoBlock(row) {
      return [
        `查询时间: ${formatDisplayTime(resolveQuotaQueryTime(row))}`,
        `账号套餐: ${formatPlanTypeLabel(resolvePlanType(row))}`,
        `当前额度: ${quotaSummary(row)}`,
        `绑定代理: ${row.proxyLabel || "直连"}`,
        `OAuth RF: ${accountHasRefreshToken(row) ? "已绑定" : "未绑定（可选）"}`,
        `Outlook邮箱: ${row.hasMailbox ? "已绑定" : ((row.accountType || "").toLowerCase() === "oauth" ? "未绑定（可选）" : "已配置")}`,
      ].join("\n");
    }

    function formatInlinePanelContent(row) {
      const head = formatAccountInfoBlock(row);
      const otpLine = mailboxOtpByAccount[row.id]
        ? `\n\n邮箱验证码: ${mailboxOtpByAccount[row.id]}`
        : "";
      if (!row?.testResult) {
        return `${head}${otpLine}\n\n异常：先点「重新登录」（等同重新走导入登录），再选代理/查询额度/开始测试`;
      }
      return `${head}${otpLine}\n\n${formatTestResult({ testStatus: row.testStatus, result: row.testResult }, { includeQuota: false })}`;
    }

    function updateImportPanels() {
      $("email-import-panel").style.display = importAccountType === "email" ? "" : "none";
      $("oauth-import-panel").style.display = importAccountType === "oauth" ? "" : "none";
      if (importAccountType !== "email") updateOAuthPanels();
    }

    function updateOAuthPanels() {
      document.querySelectorAll("[data-oauth-method]").forEach((tab) => {
        tab.classList.toggle("active", tab.dataset.oauthMethod === oauthMethod);
      });
      document.querySelectorAll(".oauth-panel").forEach((panel) => {
        panel.classList.toggle("active", panel.id === `oauth-panel-${oauthMethod}`);
      });
    }

    function accountCanReadMailbox(row) {
      return Boolean(row?.hasMailbox);
    }

    function accountCanLinkMailbox(row) {
      return (row?.accountType || "").toLowerCase() === "oauth" && !row?.hasMailbox;
    }

    function accountCanUpdateMailbox(row) {
      return (row?.accountType || "").toLowerCase() === "oauth" && Boolean(row?.hasMailbox);
    }

    function accountHasRefreshToken(row) {
      return Boolean(row?.hasRefreshToken);
    }

    function accountCanOAuthAuthorize(row) {
      if (!row || accountHasRefreshToken(row)) return false;
      return !accountNeedsReauth(row);
    }

    function accountNeedsReauth(row) {
      return accountIsAbnormal(row);
    }

    function buildMailboxPanel(row) {
      return `
        <div class="mailbox-panel" data-mailbox-panel="${row.id}">
          <strong>${row.hasMailbox ? "更新 Outlook 凭证" : "绑定 Outlook 凭证（可选）"}</strong>
          <div class="field-hint">格式：<span class="mono">email----password----clientId----refreshToken</span>。邮箱必须与本账号 <strong>${escapeHtml(row.email)}</strong> 一致，<strong>不能换成别的邮箱</strong>。仅用于读取 OpenAI 验证码；密码或 refreshToken 变了时可重填。</div>
          <textarea class="inline-mailbox-input" data-account-id="${row.id}" placeholder="email----password----clientId----refreshToken"></textarea>
          <div class="controls" style="margin-top:0;">
            <button class="button primary inline-mailbox-save-btn" data-account-id="${row.id}">保存邮箱凭证</button>
            <button class="button inline-mailbox-cancel-btn" data-account-id="${row.id}">取消</button>
          </div>
        </div>
      `;
    }

    function buildReauthPanel(row) {
      const session = reauthSessions[row.id] || {};
      const authUrl = session.authUrl || "尚未生成授权链接";
      const mode = reauthModes[row.id] || "recovery";
      const optional = mode === "optional";
      return `
        <div class="reauth-panel ${optional ? "optional-oauth" : ""}" data-reauth-panel="${row.id}">
          <strong>${optional ? "ChatGPT OAuth 授权（可选）" : "ChatGPT OAuth 重新授权"}</strong>
          <div class="field-hint">${optional
            ? "不授权也可正常测试、取号、导出。绑定 OAuth 后导出 JSON 会包含 refresh_token，便于长期自动续期。"
            : "生成授权链接并完成浏览器登录后，将回调 URL 或 code 粘贴到下方，再点击完成授权。"}</div>
          <div class="controls" style="margin-top:0;">
            <button class="button primary inline-reauth-link-btn" data-account-id="${row.id}">生成授权链接</button>
            <button class="button inline-reauth-open-btn" data-account-id="${row.id}" ${session.authUrl ? "" : "disabled"}>打开链接</button>
            <button class="button inline-reauth-copy-btn" data-account-id="${row.id}" ${session.authUrl ? "" : "disabled"}>复制链接</button>
          </div>
          <div class="auth-link-box inline-reauth-url" data-account-id="${row.id}">${authUrl}</div>
          <textarea class="inline-reauth-input" data-account-id="${row.id}" placeholder="粘贴回调 URL 或 code"></textarea>
          <div class="controls" style="margin-top:0;">
            <button class="button primary inline-reauth-complete-btn" data-account-id="${row.id}" data-reauth-mode="${mode}">
              ${optional ? "完成 OAuth 授权" : "完成授权并重新检测"}
            </button>
            <button class="button inline-reauth-cancel-btn" data-account-id="${row.id}">取消</button>
          </div>
        </div>
      `;
    }

    function buildInlineTestPanel(row) {
      const modelOptions = (testOptions.models || []).map((model) =>
        `<option value="${model}" ${model === testOptions.defaultModel ? "selected" : ""}>${model}</option>`
      ).join("");
      const exportOptions = EXPORT_FORMATS.map((item) =>
        `<option value="${item.value}">${item.label}</option>`
      ).join("");
      const proxyOptions = buildProxyOptions(row);
      return `
        <div class="test-panel" data-inline-test="${row.id}">
          <strong>测试账号：<span class="account-email-copy" data-copy-email="${escapeAttr(row.email)}" title="点击复制邮箱">${escapeHtml(row.email)}</span></strong>
          <div class="account-remark-row" data-account-id="${row.id}">
            <span class="account-remark-label">备注</span>
            <span class="account-remark-text ${row.remark ? "" : "is-empty"}" data-remark-display data-account-id="${row.id}" title="双击编辑">${escapeHtml(row.remark || "双击添加备注")}</span>
            <input class="account-remark-input" data-remark-input data-account-id="${row.id}" type="text" value="${escapeHtml(row.remark || "")}" hidden>
          </div>
          <div class="test-grid">
            <div class="field" style="margin-top:0;">
              <label>模型</label>
              <select class="inline-test-model" data-account-id="${row.id}">${modelOptions}</select>
            </div>
            <div class="field" style="margin-top:0;">
              <label>测试消息</label>
              <input class="inline-test-message" data-account-id="${row.id}" value="${testOptions.defaultMessage || "hi"}">
            </div>
            <div class="field" style="margin-top:0;">
              <label>代理</label>
              <select class="inline-test-proxy" data-account-id="${row.id}">${proxyOptions}</select>
            </div>
            <div class="field" style="margin-top:0;">
              <label>导出类型</label>
              <select class="inline-export-format" data-account-id="${row.id}">${exportOptions}</select>
            </div>
            <div class="field field-action" style="margin-top:0;">
              <label aria-hidden="true">&nbsp;</label>
              <button class="button inline-export-btn" data-account-id="${row.id}">导出文件</button>
            </div>
          </div>
          <div class="controls" style="margin-top:0;">
            <button class="button primary inline-run-test-btn" data-account-id="${row.id}">开始测试</button>
            <button class="button inline-login-btn" data-account-id="${row.id}" title="清空旧 token，按导入时同样流程重新登录（OTP+校验），需已配置代理">重新登录</button>
            <button class="button inline-query-quota-btn" data-account-id="${row.id}">查询额度</button>
            ${accountCanLinkMailbox(row) ? `<button class="button inline-open-mailbox-btn" data-account-id="${row.id}">绑定 Outlook 凭证</button>` : ""}
            ${accountCanUpdateMailbox(row) ? `<button class="button inline-open-mailbox-btn" data-account-id="${row.id}">更新 Outlook 凭证</button>` : ""}
            ${accountCanReadMailbox(row) ? `<button class="button inline-read-mailbox-btn${mailboxBusyAccountId === row.id ? " is-busy" : ""}" data-account-id="${row.id}" ${mailboxBusyAccountId === row.id ? "disabled" : ""}>${mailboxBusyAccountId === row.id ? "读取中" : "读取邮箱"}</button>` : ""}
            ${accountCanOAuthAuthorize(row) ? `<button class="button inline-open-oauth-btn" data-account-id="${row.id}">OAuth授权</button>` : ""}
            ${accountNeedsReauth(row) ? `<button class="button danger inline-open-reauth-btn" data-account-id="${row.id}">重新授权</button>` : ""}
            <button class="button priority-sale-btn inline-priority-sale-btn${row.prioritySale ? " is-on" : ""}" type="button" data-account-id="${row.id}" data-priority-sale="${row.prioritySale ? "1" : "0"}" title="${row.prioritySale ? "已优先：下次取号优先分配此账号（按开启时间排序）" : "开启后，下次用户取号将优先分配此账号"}">${row.prioritySale ? "已优先出售" : "优先出售"}</button>
            <button class="button inline-close-test-btn" data-account-id="${row.id}">关闭</button>
          </div>
          ${mailboxOpenAccountId === row.id ? buildMailboxPanel(row) : ""}
          ${reauthOpenAccountId === row.id ? buildReauthPanel(row) : ""}
          <div class="test-result inline-test-result" data-account-id="${row.id}">${formatInlinePanelContent(row)}</div>
        </div>
      `;
    }

    function formatQuotaResult(quota) {
      if (!quota) return "未查询额度";
      if (!quota.ok) return `额度查询失败: ${quota.error || "未知错误"}`;
      const lines = [
        `查询时间: ${formatDisplayTime(quota.queriedAt || "")}`,
        `账号套餐: ${formatPlanTypeLabel(quota.planType || quota.raw?.plan_type || "")}`,
        `摘要: ${quota.summary || "-"}`,
        `5h: ${quota.primaryWindow?.usedPercent ?? "-"}% / 重置 ${quota.primaryResetText || "-"}`,
        `周: ${quota.secondaryWindow?.usedPercent ?? "-"}% / 重置 ${quota.secondaryResetText || "-"}`,
      ];
      if (quota.creditsBalance) lines.push(`Credits: ${quota.creditsBalance}`);
      return lines.join("\n");
    }

    function formatLoginMode(mode) {
      const labels = {
        cache: "使用缓存 token",
        email_login: "邮箱重新登录",
        oauth: "OAuth token",
      };
      return labels[mode] || mode || "-";
    }

    function formatTestResult(data, { includeQuota = true } = {}) {
      const result = data.result || {};
      const statusKey = data.testStatus || (result.ok ? "success" : "failed");
      const lines = [
        `状态: ${testStatusLabel(statusKey)}`,
        `模型: ${result.model || "-"}`,
        `消息: ${result.message || "-"}`,
      ];
      if (result.loginMode) lines.push(`登录方式: ${formatLoginMode(result.loginMode)}`);
      if (result.totalMs != null) lines.push(`总耗时: ${result.totalMs} ms`);
      if (result.loginMs != null) lines.push(`登录耗时: ${result.loginMs} ms`);
      if (result.latencyMs != null) lines.push(`测试耗时: ${result.latencyMs} ms`);
      if (result.quotaMs != null) lines.push(`额度耗时: ${result.quotaMs} ms`);
      if (result.reply) lines.push(`回复: ${result.reply}`);
      if (result.error) lines.push(`错误: ${localizeAdminError(result.error)}`);
      if (includeQuota && result.quota) {
        lines.push("");
        lines.push("额度:");
        lines.push(formatQuotaResult(result.quota));
      } else if (includeQuota && data.quota) {
        lines.push("");
        lines.push("额度:");
        lines.push(formatQuotaResult(data.quota));
      }
      return lines.join("\n");
    }

    function renderStats(stats) {
      const pp = stats.pp || {};
      const go = stats.go || {};
      const items = stats.overview === false && stats.poolType
        ? [
            [`${POOL_LABELS[stats.poolType] || stats.poolType} · 可用账号`, stats.accountsAvailable],
            [`${POOL_LABELS[stats.poolType] || stats.poolType} · 卡密`, stats.cardsAvailable],
            [`${POOL_LABELS[stats.poolType] || stats.poolType} · 异常账号`, stats.accountsFailed],
            [`${POOL_LABELS[stats.poolType] || stats.poolType} · 已用卡密`, stats.cardsUsed],
          ]
        : [
            ["PP可用账号", pp.accountsAvailable],
            ["PP卡密", pp.cardsAvailable],
            ["PP异常账号", pp.accountsFailed],
            ["PP已用卡密", pp.cardsUsed],
            ["GO可用账号", go.accountsAvailable],
            ["GO卡密", go.cardsAvailable],
            ["GO异常账号", go.accountsFailed],
            ["GO已用卡密", go.cardsUsed],
          ];
      $("stats").innerHTML = items.map(([label, value]) =>
        `<div class="stat-card"><div class="stat-label">${label}</div><div class="stat-value">${value ?? 0}</div></div>`
      ).join("");
    }

    function renderPagination(prefix, data) {
      const total = data.total || 0;
      const page = data.page || 1;
      const totalPages = data.totalPages || 1;
      $(`${prefix}-page-info`).textContent = `第 ${page} / ${totalPages} 页，共 ${total} 条`;
      $(`${prefix}-prev`).disabled = page <= 1;
      $(`${prefix}-next`).disabled = page >= totalPages;
    }

    function isInteractiveTarget(target) {
      return Boolean(target.closest("button, input, select, textarea, a, label, .account-email-copy"));
    }

    async function copyAccountEmail(email) {
      const text = String(email || "").trim();
      if (!text) return;
      await navigator.clipboard.writeText(text);
      showToast(`已复制邮箱：${text}`, "success", 2000);
    }

    function syncAccountsSelectAllCheckbox(rows) {
      const selectAll = $("accounts-select-all");
      if (!selectAll) return;
      const items = rows || [];
      selectAll.checked = items.length > 0 && items.every((row) => selectedAccountIds.has(row.id));
      selectAll.indeterminate = !selectAll.checked && items.some((row) => selectedAccountIds.has(row.id));
    }

    function syncCardsSelectAllCheckbox(rows) {
      const selectAll = $("cards-select-all");
      if (!selectAll) return;
      const items = rows || [];
      selectAll.checked = items.length > 0 && items.every((row) => selectedCardCodes.has(row.code));
      selectAll.indeterminate = !selectAll.checked && items.some((row) => selectedCardCodes.has(row.code));
    }

    function selectAccountRow(accountId) {
      if (!accountId) return;
      selectedAccountId = accountId;
      selectedAccountIds.clear();
      selectedAccountIds.add(accountId);
      renderAccounts({ items: listState.lastAccounts || [], ...(listState.accountsMeta || {}) });
    }

    function selectCardRow(code) {
      if (!code) return;
      selectedCardCodes.clear();
      selectedCardCodes.add(code);
      renderCards({ items: listState.lastCards || [], ...(listState.cardsMeta || {}) });
    }

    function toggleAccountExpand(row) {
      if (!row) return;
      testingAccount = testingAccount && testingAccount.id === row.id ? null : row;
      if (testingAccount) {
        sessionStorage.setItem(EXPANDED_ACCOUNT_KEY, testingAccount.id);
        loadTestOptions().catch(() => {});
      } else {
        sessionStorage.removeItem(EXPANDED_ACCOUNT_KEY);
      }
      renderAccounts({ items: listState.lastAccounts || [], ...(listState.accountsMeta || {}) });
    }

    function renderCards(data) {
      const rows = data.items || [];
      listState.lastCards = rows;
      listState.cardsMeta = {
        total: data.total,
        page: data.page,
        pageSize: data.pageSize,
        totalPages: data.totalPages,
      };
      $("cards-table").innerHTML = rows.length ? rows.map((row) => `
        <tr class="data-row card-row ${selectedCardCodes.has(row.code) ? "row-selected" : ""}" data-card-row="${row.code}">
          <td class="col-check"><input type="checkbox" class="card-check" data-card-code="${row.code}" ${selectedCardCodes.has(row.code) ? "checked" : ""}></td>
          <td class="mono">${row.code}</td>
          <td><span class="pill ${row.status}">${row.status === "available" ? "可用" : "已用"}</span></td>
          <td>${row.accountEmail || "-"}</td>
          <td>${row.createdAt || "-"}</td>
          <td><button class="button small danger" data-delete-card="${row.code}">删除</button></td>
        </tr>
      `).join("") : `<tr><td colspan="6">暂无卡密</td></tr>`;
      syncCardsSelectAllCheckbox(rows);
      renderPagination("cards", data);
    }

    function renderAccounts(data) {
      const rows = data.items || [];
      $("accounts-table").innerHTML = rows.length ? rows.map((row) => {
        const expanded = testingAccount && testingAccount.id === row.id;
        const selected = selectedAccountId === row.id || selectedAccountIds.has(row.id);
        const poolStatus = accountPoolStatus(row);
        return `
        <tr class="data-row account-row ${selected ? "row-selected" : ""}" data-account-row="${row.id}">
          <td class="col-check"><input type="checkbox" class="account-check" data-account-id="${row.id}" ${selectedAccountIds.has(row.id) ? "checked" : ""}></td>
          <td><span class="account-email-copy mono" data-copy-email="${escapeAttr(row.email)}" title="点击复制邮箱">${escapeHtml(row.email)}</span></td>
          <td>${accountTypeLabel(row.accountType)} · ${groupNameLabel(row.groupName)}</td>
          <td><span class="pill ${poolStatus.className}">${poolStatus.label}</span></td>
          <td class="quota-text">${quotaSummary(row)}${resolvePlanType(row) ? ` · ${formatPlanTypeLabel(resolvePlanType(row))}` : ""}</td>
          <td><span class="pill ${testStatusClass(row.testStatus)}">${testStatusLabel(row.testStatus)}</span></td>
          <td class="mono">${row.cardCode || "-"}</td>
          <td>${formatDisplayTime(row.createdAt, "-")}</td>
          <td>${formatDisplayTime(row.assignedAt, "-")}</td>
          <td><button class="button small danger" data-delete-account="${row.id}">删除</button></td>
        </tr>
        ${expanded ? `<tr class="account-detail-row"><td colspan="10">${buildInlineTestPanel(row)}</td></tr>` : ""}
      `;
      }).join("") : `<tr><td colspan="10">暂无账号</td></tr>`;
      syncAccountsSelectAllCheckbox(rows);
      renderPagination("accounts", data);
    }

    function initAutoTestIntervalSelect() {
      const select = $("setting-auto-test-interval");
      if (!select || select.dataset.ready === "1") return;
      select.innerHTML = `<option value="0">关闭</option>${Array.from({ length: 24 }, (_, index) => {
        const hours = index + 1;
        return `<option value="${hours}">每 ${hours} 小时</option>`;
      }).join("")}`;
      select.dataset.ready = "1";
    }

    function renderAutoTestStatus(settings) {
      const box = $("auto-test-status");
      const btn = $("auto-test-now-btn");
      if (btn) {
        const running = !!settings.autoTestRunning;
        btn.disabled = running;
        btn.textContent = running ? "测试中…" : "立即测试";
      }
      if (!box) return;
      const interval = Number(settings.autoTestIntervalHours || 0);
      if (interval <= 0) {
        box.textContent = "已关闭 · 与账号「开始测试」相同，测试全部 PP/GO 账号";
        return;
      }
      const parts = [`每 ${interval} 小时执行一次`];
      if (settings.autoTestRunning) parts.push("当前正在自动测试中…");
      if (settings.autoTestLastRunAt) parts.push(`上次：${formatDisplayTime(settings.autoTestLastRunAt, "-")}`);
      if (settings.autoTestNextRunAt) {
        parts.push(
          settings.autoTestNextRunAt === "即将执行" || settings.autoTestNextRunAt === "pending"
            ? "下次：即将执行"
            : `下次：${formatDisplayTime(settings.autoTestNextRunAt, "-")}`,
        );
      }
      if (settings.autoTestLastSummary) parts.push(`结果：${settings.autoTestLastSummary}`);
      box.textContent = parts.join(" · ");
    }

    function stopAutoTestPoll() {
      if (autoTestPollTimer) {
        clearInterval(autoTestPollTimer);
        autoTestPollTimer = null;
      }
    }

    function startAutoTestPoll() {
      stopAutoTestPoll();
      autoTestPollTimer = setInterval(async () => {
        try {
          const res = await adminFetch("/api/admin/settings");
          const settings = await readAdminJson(res, "刷新状态失败");
          if (!res.ok) return;
          renderAutoTestStatus(settings);
          const btn = $("auto-test-now-btn");
          if (settings.autoTestRunning) {
            if (btn) {
              btn.disabled = true;
              btn.textContent = "测试中…";
            }
            return;
          }
          stopAutoTestPoll();
          if (btn) {
            btn.disabled = false;
            btn.textContent = "立即测试";
          }
          if (settings.autoTestLastSummary) {
            showToast(`测试完成：${settings.autoTestLastSummary}`, "success", 4000);
          }
          await loadAccounts().catch(() => {});
        } catch {
          /* 轮询静默失败 */
        }
      }, 2500);
    }

    async function runAutoTestNow() {
      const button = $("auto-test-now-btn");
      if (button?.disabled) return;
      if (button) {
        button.disabled = true;
        button.textContent = "启动中…";
      }
      try {
        const res = await adminFetch("/api/admin/auto-test/run", { method: "POST", body: "{}" });
        const data = await readAdminJson(res, "启动测试失败");
        if (!res.ok) throw new Error(data.error || data.reason || "启动测试失败");
        showToast(data.message || "已开始测试全部账号", "success", 3000);
        await loadSettings();
        startAutoTestPoll();
      } catch (error) {
        showToast(error.message || "启动测试失败", "error");
        if (button) {
          button.disabled = false;
          button.textContent = "立即测试";
        }
      }
    }

    function renderApiSettings(settings) {
      const keyInput = $("setting-api-key");
      const baseNode = $("setting-api-base");
      const aboutBaseNode = $("about-api-base");
      const publicBaseInput = $("setting-public-base-url");
      const aboutList = $("about-api-list");
      if (!keyInput) return;
      const key = settings.apiGatewayKey || "";
      keyInput.value = key;
      if (publicBaseInput) publicBaseInput.value = settings.publicBaseUrl || "";
      const baseUrl = settings.apiGatewayBaseUrl || "-";
      if (baseNode) {
        baseNode.textContent = settings.publicBaseUrl
          ? baseUrl
          : `${baseUrl}${settings.apiGatewayBaseUrlAuto ? "（自动识别）" : ""}`;
      }
      if (aboutBaseNode) aboutBaseNode.textContent = baseUrl;
      const providers = settings.apiProviders || [];
      if (aboutList) {
        aboutList.innerHTML = providers.length
          ? providers.map((item) => `
            <div class="api-provider-card">
              <strong>${escapeHtml(item.name || item.id || "-")}</strong>
              <div class="mono">${escapeHtml(item.routePrefix || "")} → ${escapeHtml(item.exampleUrl || "-")}</div>
              <div class="field-hint">${escapeHtml(item.note || "")}</div>
            </div>
          `).join("")
          : `<div class="field-hint">暂无 API 路由信息，请刷新页面或重启服务。</div>`;
      }
    }

    function loadSavedLogin() {
      const remember = localStorage.getItem(REMEMBER_PASSWORD_KEY) === "1";
      const rememberBox = $("remember-password");
      const passwordInput = $("admin-password");
      if (rememberBox) rememberBox.checked = remember;
      if (remember && passwordInput) {
        passwordInput.value = localStorage.getItem(SAVED_PASSWORD_KEY) || "";
      }
    }

    function persistRememberPassword(password) {
      const remember = Boolean($("remember-password")?.checked);
      if (remember) {
        localStorage.setItem(REMEMBER_PASSWORD_KEY, "1");
        localStorage.setItem(SAVED_PASSWORD_KEY, password || "");
      } else {
        localStorage.removeItem(REMEMBER_PASSWORD_KEY);
        localStorage.removeItem(SAVED_PASSWORD_KEY);
      }
    }

    function renderSettings(settings) {
      $("setting-proxy").value = settings.proxyPoolText || "";
      $("proxy-count").textContent = String(settings.proxyCount || 0);
      $("setting-test-models").value = settings.testModelsText || (settings.models || []).join("\n");
      $("setting-default-model").value = settings.defaultModel || "";
      $("setting-default-message").value = settings.defaultMessage || "hi";
      $("setting-auto-test-interval").value = String(settings.autoTestIntervalHours ?? 0);
      renderAutoTestStatus(settings);
      renderApiSettings(settings);
      testOptions = {
        ...testOptions,
        models: settings.models || testOptions.models,
        defaultModel: settings.defaultModel || testOptions.defaultModel,
        defaultMessage: settings.defaultMessage || testOptions.defaultMessage,
        proxyOptions: settings.proxyOptions || testOptions.proxyOptions,
      };
    }

    async function loadSettings() {
      const res = await adminFetch("/api/admin/settings");
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "加载设置失败");
      renderSettings(data);
    }

    function renderProxyTestResults(data) {
      const box = $("proxy-test-result");
      if (!box) return;
      const lines = [
        `测试完成：${data.summary || "-"}`,
        `耗时 ${data.durationMs ?? "-"} ms`,
        "",
      ];
      for (const item of data.results || []) {
        if (item.ok) {
          lines.push(
            `✓ ${item.label} | ${item.latencyMs}ms | IP ${item.exitIp || "-"} | ChatGPT ${item.chatgptStatus}`
          );
        } else {
          lines.push(`✗ ${item.label} | ${item.latencyMs ?? "-"}ms | ${item.error || "不可用"}`);
        }
      }
      box.hidden = false;
      box.textContent = lines.join("\n");
      box.classList.toggle("ok-line", (data.failed || 0) === 0);
      box.classList.toggle("fail-line", (data.failed || 0) > 0);
    }

    async function testProxyPool() {
      const button = $("test-proxy-btn");
      const box = $("proxy-test-result");
      if (button) {
        button.disabled = true;
        button.textContent = "测试中...";
      }
      if (box) {
        box.hidden = false;
        box.textContent = "正在测试代理池，请稍候...";
        box.classList.remove("ok-line", "fail-line");
      }
      try {
        const res = await adminFetch("/api/admin/proxy/test", {
          method: "POST",
          body: JSON.stringify({ proxyPoolText: $("setting-proxy").value }),
        });
        const data = await readAdminJson(res, "代理测试失败");
        if (!res.ok) throw new Error(data.error || "代理测试失败");
        renderProxyTestResults(data);
        showToast(data.summary || "代理测试完成", (data.failed || 0) > 0 ? "error" : "success");
      } catch (error) {
        if (box) {
          box.hidden = false;
          box.textContent = localizeAdminError(error.message, "代理测试失败");
          box.classList.add("fail-line");
        }
        showToast(error.message || "代理测试失败", "error");
      } finally {
        if (button) {
          button.disabled = false;
          button.textContent = "测试代理池";
        }
      }
    }

    async function saveSettings(options = {}) {
      const payload = {
        proxyPoolText: $("setting-proxy").value,
        testModelsText: $("setting-test-models").value,
        defaultTestModel: $("setting-default-model").value,
        defaultTestMessage: $("setting-default-message").value,
        autoTestIntervalHours: Number($("setting-auto-test-interval").value || 0),
        publicBaseUrl: ($("setting-public-base-url")?.value || "").trim(),
      };
      const password = $("setting-password").value;
      const confirmPassword = $("setting-password-confirm").value;
      if (password || confirmPassword) {
        payload.newPassword = password;
        payload.confirmPassword = confirmPassword;
      }
      if (options.clearPassword) payload.clearPassword = true;
      const res = await adminFetch("/api/admin/settings", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      const data = await readAdminJson(res, "保存设置失败");
      if (!res.ok) throw new Error(data.error || "保存设置失败");
      $("setting-password").value = "";
      $("setting-password-confirm").value = "";
      await loadSettings();
      await loadTestOptions();
      await loadAccounts().catch(() => {});
      const settings = data.settings || data;
      const pruned = settings.proxiesPruned || {};
      const prunedTotal = Number(pruned.total ?? 0);
      const backfill = Number(settings.proxiesBackfilled ?? 0);
      if (prunedTotal > 0 || backfill > 0) {
        const parts = ["设置已保存"];
        if (prunedTotal > 0) {
          parts.push(`已处理 ${prunedTotal} 个失效代理（${pruned.reassigned || 0} 个重分，${pruned.cleared || 0} 个改直连）`);
        }
        if (backfill > 0) parts.push(`为 ${backfill} 个账号新分配代理`);
        showToast(parts.join("，"), "success", 4500);
      }
      return data;
    }

    async function loadStats() {
      const res = await adminFetch("/api/admin/dashboard");
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "加载失败");
      renderStats(data.stats || {});
    }

    async function loadCards() {
      const { page, pageSize, poolType } = listState.cards;
      const res = await adminFetch(`/api/admin/cards?page=${page}&pageSize=${pageSize}&poolType=${encodeURIComponent(poolType || "pp")}`);
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "加载卡密失败");
      listState.cards.page = data.page || page;
      renderCards(data);
    }

    async function loadAccounts() {
      const { page, pageSize, group } = listState.accounts;
      const poolType = currentAccountPoolType();
      const groupQuery = group && group !== "all" ? `&group=${encodeURIComponent(group)}` : "";
      const res = await adminFetch(`/api/admin/accounts?page=${page}&pageSize=${pageSize}&poolType=${encodeURIComponent(poolType)}${groupQuery}`);
      const data = await readAdminJson(res, "加载账号失败");
      if (!res.ok) throw new Error(data.error || "加载账号失败");
      listState.accounts.page = data.page || page;
      listState.lastAccounts = data.items || [];
      listState.accountsMeta = {
        total: data.total,
        page: data.page,
        pageSize: data.pageSize,
        totalPages: data.totalPages,
        group: data.group || group || "all",
      };
      if (savedExpandedAccountId && !testingAccount) {
        const savedRow = listState.lastAccounts.find((item) => item.id === savedExpandedAccountId);
        if (savedRow) testingAccount = savedRow;
      }
      if (testingAccount) {
        const refreshed = listState.lastAccounts.find((item) => item.id === testingAccount.id);
        if (refreshed) testingAccount = refreshed;
      }
      updateAccountGroupTabs();
      renderAccounts(data);
      if (hasPendingAccounts(listState.lastAccounts)) scheduleAccountPolling();
    }

    async function loadTestOptions() {
      const res = await adminFetch("/api/admin/accounts/test-options");
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "加载测试选项失败");
      testOptions = {
        ...testOptions,
        ...data,
        proxyOptions: data.proxyOptions?.length ? data.proxyOptions : testOptions.proxyOptions,
      };
      const sync = data.proxySync || {};
      const synced = Number(sync.proxiesPruned?.total || 0) + Number(sync.proxiesBackfilled || 0);
      if (synced > 0) {
        await loadAccounts().catch(() => {});
      } else if (testingAccount) {
        const refreshed = (listState.lastAccounts || []).find((item) => item.id === testingAccount.id);
        if (refreshed) {
          testingAccount = refreshed;
          renderAccounts({ items: listState.lastAccounts || [], ...(listState.accountsMeta || {}) });
        }
      }
    }

    function currentImportRemark() {
      return ($("import-remark")?.value || "").trim();
    }

    async function toggleAccountPrioritySale(accountId, enable) {
      const res = await adminFetch("/api/admin/accounts/priority-sale", {
        method: "POST",
        body: JSON.stringify({ accountId, enabled: enable }),
      });
      const data = await readAdminJson(res, "设置优先出售失败");
      if (!res.ok) throw new Error(data.error || "设置优先出售失败");
      const on = !!data.prioritySale;
      for (const row of listState.lastAccounts || []) {
        if (row.id === accountId) {
          row.prioritySale = on;
          row.prioritySaleAt = data.prioritySaleAt || null;
        }
      }
      if (testingAccount && testingAccount.id === accountId) {
        testingAccount.prioritySale = on;
        testingAccount.prioritySaleAt = data.prioritySaleAt || null;
      }
      return data;
    }

    async function saveAccountRemark(accountId, remark) {
      const res = await adminFetch("/api/admin/accounts/remark", {
        method: "POST",
        body: JSON.stringify({ accountId, remark: remark || "" }),
      });
      const data = await readAdminJson(res, "保存备注失败");
      if (!res.ok) throw new Error(data.error || "保存备注失败");
      const text = String(data.remark || "").trim();
      for (const row of listState.lastAccounts || []) {
        if (row.id === accountId) row.remark = text;
      }
      if (testingAccount && testingAccount.id === accountId) testingAccount.remark = text;
      return text;
    }

    function beginRemarkEdit(displayEl) {
      const accountId = displayEl.dataset.accountId;
      const input = document.querySelector(`[data-remark-input][data-account-id="${accountId}"]`);
      if (!input) return;
      input.hidden = false;
      displayEl.hidden = true;
      input.value = displayEl.classList.contains("is-empty") ? "" : displayEl.textContent.trim();
      input.focus();
      input.select();
    }

    async function finishRemarkEdit(inputEl) {
      const accountId = inputEl.dataset.accountId;
      const display = document.querySelector(`[data-remark-display][data-account-id="${accountId}"]`);
      const value = inputEl.value.trim();
      try {
        await saveAccountRemark(accountId, value);
        if (display) {
          display.textContent = value || "双击添加备注";
          display.classList.toggle("is-empty", !value);
          display.hidden = false;
        }
        inputEl.hidden = true;
        showToast("备注已保存", "success");
      } catch (error) {
        showToast(error.message || "保存失败", "error");
        if (display) display.hidden = false;
        inputEl.hidden = true;
      }
    }

    async function runImportFast(payload, { clearInputs } = {}) {
      const res = await adminFetch("/api/admin/accounts/import", {
        method: "POST",
        body: JSON.stringify({
          ...payload,
          remark: payload.remark != null ? payload.remark : currentImportRemark(),
          poolType: currentAccountPoolType(),
          background: true,
        }),
      });
      const data = await readAdminJson(res, "导入失败");
      if (!res.ok) throw new Error(data.error || "导入失败");
      if (typeof clearInputs === "function") clearInputs();
      await loadStats();
      await loadAccounts();
      if ((data.queued || 0) > 0) scheduleAccountPolling();
      const skipped = data.skipped ? `，跳过 ${data.skipped} 个` : "";
      showToast(`已导入 ${data.imported || 0} 个${skipped}，后台检测中`, "success");
      return data;
    }

    async function importOAuth(payload) {
      return runImportFast({ accountType: "oauth", ...payload });
    }

    async function checkServerHealth() {
      try {
        const res = await fetch("/api/admin/health");
        const data = await readAdminJson(res, "健康检查失败");
        if (!res.ok) throw new Error(data.error || "健康检查失败");
        const features = data.features || [];
        if (!features.includes("sse-text-v2")) {
          showToast("后台服务版本过旧，请运行 tools/restart_admin.ps1 重启后再测试", "error", 6000);
        }
        return data;
      } catch (error) {
        showToast(error.message || "无法连接后台服务", "error", 5000);
        return null;
      }
    }

    async function runAccountProxyUpdate(accountId, proxy) {
      const res = await adminFetch("/api/admin/accounts/proxy", {
        method: "POST",
        body: JSON.stringify({ accountId, proxy }),
      });
      const data = await readAdminJson(res, "更新代理失败");
      if (!res.ok) throw new Error(data.error || "更新代理失败");
      const row = (listState.lastAccounts || []).find((item) => item.id === accountId);
      if (row) {
        row.assignedProxy = data.assignedProxy || "";
        row.proxyLabel = data.proxyLabel || "直连";
      }
      showToast(`代理已设为 ${data.proxyLabel || "直连"}`, "success", 1800);
      return data;
    }

    async function runAccountTest(accountId, model, message) {
      const resultBox = document.querySelector(`.inline-test-result[data-account-id="${accountId}"]`);
      if (resultBox) resultBox.textContent = "测试中，请稍候...";
      const res = await adminFetch("/api/admin/accounts/test", {
        method: "POST",
        body: JSON.stringify({ accountId, model, message: message || "hi" }),
      });
      const data = await readAdminJson(res, "测试失败");
      if (!res.ok) {
        const err = new Error(data.detail || data.error || "测试失败");
        err.apiData = data;
        throw err;
      }
      await loadAccounts();
      showToast(data.result?.ok ? "测试通过" : localizeAdminError(data.result?.error, "测试失败"), data.result?.ok ? "success" : "error", data.result?.ok ? 1500 : 5000);
      return data;
    }

    function formatLoginResult(data) {
      if (!data?.ok) return `登录失败: ${data?.error || "未知错误"}`;
      const lines = [
        "重新登录成功（已校验额度）",
        `方式: ${formatLoginMode(data.loginMode)}`,
        `登录耗时: ${data.loginMs ?? "-"}ms`,
        `代理: ${data.proxyLabel || "-"}`,
      ];
      if (data.proxyAssigned) lines.push("已从代理池自动绑定代理");
      if (data.proxyRotated) lines.push("已自动切换为代理池中的下一个代理");
      if (data.materialRefreshed) lines.push("已从库内素材刷新邮箱密码/令牌");
      if (data.quotaSummary) lines.push(`额度: ${data.quotaSummary}`);
      if (data.quota) {
        lines.push("");
        lines.push("额度详情:");
        lines.push(formatQuotaResult(data.quota));
      }
      if (data.test) {
        lines.push("");
        lines.push("自动测试结果:");
        lines.push(formatTestResult(data.test, { includeQuota: false }));
      }
      return lines.join("\n");
    }

    async function runAccountLogin(accountId) {
      const resultBox = document.querySelector(`.inline-test-result[data-account-id="${accountId}"]`);
      const model = document.querySelector(`.inline-test-model[data-account-id="${accountId}"]`)?.value;
      const message = document.querySelector(`.inline-test-message[data-account-id="${accountId}"]`)?.value;
      const proxy = document.querySelector(`.inline-test-proxy[data-account-id="${accountId}"]`)?.value ?? "";
      if (resultBox) {
        resultBox.textContent = "重新登录中（等同重新导入：清 token、刷新素材、走 OTP）…\n成功后将自动查额度并测试";
      }
      const res = await adminFetch("/api/admin/accounts/login", {
        method: "POST",
        body: JSON.stringify({
          accountId,
          force: true,
          autoFollowUp: true,
          proxy,
          model,
          message: message || "hi",
        }),
      });
      const data = await readAdminJson(res, "重新登录失败");
      if (!res.ok) {
        const err = new Error(data.detail || data.error || "重新登录失败");
        err.apiData = data;
        throw err;
      }
      if (resultBox) resultBox.textContent = formatLoginResult(data);
      await loadAccounts();
      const testOk = data.testOk ?? (String(data.testStatus || "").toLowerCase() === "success");
      showToast(
        testOk
          ? `重新登录并测试通过（${formatLoginMode(data.loginMode)}）`
          : `重新登录成功，但自动测试未通过`,
        testOk ? "success" : "error",
        4500,
      );
      return data;
    }

    async function runAccountQuota(accountId) {
      const resultBox = document.querySelector(`.inline-test-result[data-account-id="${accountId}"]`);
      if (resultBox) resultBox.textContent = "查询额度中...";
      const res = await adminFetch("/api/admin/accounts/quota", {
        method: "POST",
        body: JSON.stringify({ accountId }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "查询额度失败");
      await loadAccounts();
      const refreshedBox = document.querySelector(`.inline-test-result[data-account-id="${accountId}"]`);
      if (refreshedBox) refreshedBox.textContent = formatQuotaResult(data.quota);
      showToast(data.quota?.ok ? "额度已更新" : "额度查询失败", data.quota?.ok ? "success" : "error");
      return data;
    }

    async function runAccountMailboxLink(accountId) {
      const material = document.querySelector(`.inline-mailbox-input[data-account-id="${accountId}"]`)?.value || "";
      if (!material.trim()) throw new Error("请粘贴邮箱素材");
      const res = await adminFetch("/api/admin/accounts/mailbox-link", {
        method: "POST",
        body: JSON.stringify({ accountId, material }),
      });
      const data = await readAdminJson(res, "绑定邮箱失败");
      if (!res.ok) throw new Error(data.error || "绑定邮箱失败");
      mailboxOpenAccountId = "";
      await loadAccounts();
      showToast(`Outlook 凭证已保存：${data.mailboxEmail || data.email}`, "success");
      return data;
    }

    async function runAccountMailboxOtp(accountId) {
      const row = (listState.lastAccounts || []).find((item) => item.id === accountId);
      const email = row?.email || accountId;
      mailboxBusyAccountId = accountId;
      renderAccounts({ items: listState.lastAccounts || [], ...(listState.accountsMeta || {}) });
      try {
        const res = await adminFetch("/api/admin/accounts/otp", {
          method: "POST",
          body: JSON.stringify({ accountId }),
        });
        const data = await readAdminJson(res, "读取失败");
        if (!res.ok) throw new Error(data.error || "读取失败");
        mailboxOtpByAccount[accountId] = data.otp || "";
        showToast(`读取成功：${data.email || email} · ${data.otp || "-"}`, "success", 3500);
        return data;
      } catch (error) {
        showToast(error.message || `读取失败：${email}`, "error", 4500);
        throw error;
      } finally {
        mailboxBusyAccountId = "";
        renderAccounts({ items: listState.lastAccounts || [], ...(listState.accountsMeta || {}) });
      }
    }

    function downloadBase64File(filename, contentBase64, mimeType = "application/octet-stream") {
      const binary = atob(contentBase64);
      const bytes = new Uint8Array(binary.length);
      for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
      const blob = new Blob([bytes], { type: mimeType });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    }

    async function runAccountExport(accountId) {
      const format = document.querySelector(`.inline-export-format[data-account-id="${accountId}"]`)?.value || "sub2api";
      const res = await adminFetch("/api/admin/accounts/export", {
        method: "POST",
        body: JSON.stringify({ accountId, format }),
      });
      const data = await readAdminJson(res, "导出失败");
      if (!res.ok) throw new Error(data.error || "导出失败");
      if (!data.contentBase64) throw new Error("导出失败：服务器未返回文件");
      downloadBase64File(data.filename || "export.json", data.contentBase64, data.mimeType || "application/octet-stream");
      showToast(`已导出 ${data.email || accountId}`, "success");
      return data;
    }

    async function generateReauthLink(accountId) {
      const res = await adminFetch("/api/admin/openai/generate-auth-url", { method: "POST", body: "{}" });
      const data = await readAdminJson(res, "生成授权链接失败");
      if (!res.ok) throw new Error(data.error || "生成授权链接失败");
      reauthSessions[accountId] = {
        sessionId: data.sessionId || "",
        state: data.state || "",
        authUrl: data.authUrl || "",
      };
      reauthOpenAccountId = accountId;
      renderAccounts({ items: listState.lastAccounts || [], ...(listState.accountsMeta || {}) });
      showToast("授权链接已生成", "success");
      return data;
    }

    async function runAccountReauth(accountId, { optional = false } = {}) {
      const session = reauthSessions[accountId] || {};
      const authInput = document.querySelector(`.inline-reauth-input[data-account-id="${accountId}"]`)?.value || "";
      if (!authInput.trim()) throw new Error("请先粘贴回调 URL 或 code");
      const endpoint = optional ? "/api/admin/accounts/oauth-link" : "/api/admin/accounts/reauthorize";
      const res = await adminFetch(endpoint, {
        method: "POST",
        body: JSON.stringify({
          accountId,
          accountType: "oauth",
          oauthMethod: "manual",
          sessionId: session.sessionId || "",
          state: session.state || "",
          authInput,
        }),
      });
      const failLabel = optional ? "OAuth 授权失败" : "重新授权失败";
      const data = await readAdminJson(res, failLabel);
      if (!res.ok) throw new Error(data.error || failLabel);
      delete reauthSessions[accountId];
      delete reauthModes[accountId];
      reauthOpenAccountId = "";
      await loadStats();
      await loadAccounts();
      if (!optional) scheduleAccountPolling();
      showToast(
        optional ? "OAuth 已绑定，导出将包含 refresh_token" : "OAuth 授权已更新，后台重新检测中",
        "success",
        3000,
      );
      return data;
    }

    async function deleteAccountCore(accountId) {
      const attempts = [
        { url: "/api/admin/accounts/delete", body: { accountId } },
        { url: "/api/admin/accounts/import", body: { action: "delete", accountId } },
      ];
      let lastError = "删除失败";
      for (const attempt of attempts) {
        const res = await adminFetch(attempt.url, {
          method: "POST",
          body: JSON.stringify(attempt.body),
        });
        const data = await readAdminJson(res, lastError);
        if (res.ok) return;
        lastError = data.error || lastError;
        if (res.status !== 404) break;
      }
      throw new Error(lastError);
    }

    async function deleteAccount(accountId, email) {
      if (!await showConfirm({
        title: "删除账号",
        message: `确定删除账号 ${email} 吗？删除后不可恢复。`,
        confirmText: "删除",
        danger: true,
      })) return;
      await deleteAccountCore(accountId);
      if (testingAccount && testingAccount.id === accountId) {
        testingAccount = null;
        sessionStorage.removeItem(EXPANDED_ACCOUNT_KEY);
      }
      selectedAccountIds.delete(accountId);
      if (selectedAccountId === accountId) selectedAccountId = "";
      await loadDashboard();
    }

    async function deleteSelectedAccounts() {
      const ids = [...selectedAccountIds];
      if (!ids.length) {
        showToast("请先勾选账号", "error");
        return;
      }
      if (!await showConfirm({
        title: "批量删除账号",
        message: `确定删除选中的 ${ids.length} 个账号吗？删除后不可恢复。`,
        confirmText: "全部删除",
        danger: true,
      })) return;
      let deleted = 0;
      let failed = 0;
      for (const accountId of ids) {
        try {
          await deleteAccountCore(accountId);
          selectedAccountIds.delete(accountId);
          if (selectedAccountId === accountId) selectedAccountId = "";
          if (testingAccount && testingAccount.id === accountId) {
            testingAccount = null;
            sessionStorage.removeItem(EXPANDED_ACCOUNT_KEY);
          }
          deleted += 1;
        } catch (error) {
          failed += 1;
        }
      }
      await loadDashboard();
      showToast(
        failed ? `已删除 ${deleted} 个，失败 ${failed} 个` : `已删除 ${deleted} 个账号`,
        failed ? "error" : "success",
      );
    }

    async function loadDashboard() {
      fillPageSizeSelect("cards-page-size", listState.cards.pageSize);
      fillPageSizeSelect("accounts-page-size", listState.accounts.pageSize);
      await checkServerHealth();
      await Promise.all([loadStats(), loadSettings(), loadTestOptions(), loadCards(), loadAccounts(), loadVersionBadge()]);
    }

    let versionInfoCache = null;

    function renderVersionBadge(info, { highlightUpdate = false } = {}) {
      const btn = $("version-btn");
      if (!btn || !info) return;
      btn.textContent = `v${info.version || "?"}`;
      const showDot = highlightUpdate && !!info.updateAvailable;
      btn.classList.toggle("has-update", showDot);
      btn.title = showDot ? "有新版本，点击查看" : "点击查看版本（不自动检测 GitHub）";
    }

    async function loadAboutVersion() {
      const node = $("about-app-version");
      if (!node) return;
      try {
        const res = await adminFetch("/api/admin/version");
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "加载失败");
        node.textContent = `v${data.version || "?"}`;
      } catch {
        node.textContent = "未知";
      }
    }

    async function loadVersionBadge() {
      try {
        const res = await adminFetch("/api/admin/version");
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "版本加载失败");
        versionInfoCache = data;
        renderVersionBadge(data, { highlightUpdate: false });
      } catch (_) {
        /* 忽略版本加载失败，不影响仪表盘 */
      }
    }

    function closeVersionModal() {
      const backdrop = $("version-modal");
      if (backdrop) backdrop.classList.remove("show");
    }

    function escapeHtml(text) {
      return String(text || "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
    }

    function renderVersionModalBody(info) {
      const remote = info.remote || {};
      const remoteChecked = !!(remote.tag || remote.available === false);
      const latest = remote.tag ? `v${remote.tag}` : (remoteChecked ? "未知" : "未检查");
      const statusText = !remoteChecked
        ? "请点击「检查更新」"
        : (info.updateAvailable
          ? "发现新版本"
          : (info.upToDate ? "已是最新" : "无法对比远程版本"));
      const readiness = info.updateReadiness || {};
      const envReady = readiness.ready !== false;
      const canRunUpdate = !!(remoteChecked && info.selfUpdateEnabled && info.updateAvailable && envReady);
      const updateTip = !info.selfUpdateEnabled
        ? "未启用 ENABLE_SELF_UPDATE"
        : (!envReady ? (readiness.issues || []).join("；") : (info.updateAvailable ? "独立更新容器拉代码并重建 Web（期间可能短暂 502）" : (info.upToDate ? "已是最新，无需更新" : "暂无法确认是否有新版本")));
      const updateBtnHtml = `<button class="button primary" type="button" id="version-update-btn"${canRunUpdate ? "" : " disabled"} title="${escapeHtml(updateTip)}">一键更新</button>`;
      const bodyHtml = [
        `<div class="version-row"><span>当前版本</span><strong>v${escapeHtml(info.version)}</strong></div>`,
        `<div class="version-row"><span>GitHub 最新</span><strong>${escapeHtml(latest)}</strong></div>`,
        `<div class="version-row"><span>状态</span><strong>${escapeHtml(statusText)}</strong></div>`,
        remote.htmlUrl ? `<p class="version-note"><a href="${escapeHtml(remote.htmlUrl)}" target="_blank" rel="noopener">查看 GitHub 发布说明</a></p>` : "",
        remote.body ? `<p class="version-note">${escapeHtml(remote.body.slice(0, 600))}${remote.body.length > 600 ? "…" : ""}</p>` : "",
        readiness.hostBindPath
          ? `<p class="version-note">宿主机路径：<code>${escapeHtml(readiness.hostBindPath)}</code></p>`
          : "",
        (!envReady && readiness.issues && readiness.issues.length)
          ? `<p class="version-note" style="color:#c62828;">无法一键更新：${escapeHtml(readiness.issues.join("；"))}</p>`
          : "",
        `<div class="controls" style="margin-top:4px;">`,
        `<button class="button" type="button" id="version-check-btn">检查更新</button>`,
        `<button class="button" type="button" id="version-backup-btn">备份数据库</button>`,
        updateBtnHtml,
        `</div>`,
        `<div class="version-progress-wrap" id="version-progress-wrap" hidden>`,
        `  <div class="version-progress-track"><div class="version-progress-bar" id="version-progress-bar"></div></div>`,
        `  <p class="version-progress-label" id="version-progress-label"></p>`,
        `</div>`,
        `<pre class="version-log" id="version-update-log" hidden></pre>`,
      ].join("");
      $("version-modal-body").innerHTML = bodyHtml;
      $("version-check-btn")?.addEventListener("click", () => refreshVersionModal(true));
      $("version-backup-btn")?.addEventListener("click", () => runDatabaseBackup());
      const updateBtn = $("version-update-btn");
      if (updateBtn && !updateBtn.disabled) {
        updateBtn.addEventListener("click", () => runSelfUpdate());
      }
    }

    async function refreshVersionModal(showToastOnSuccess) {
      $("version-modal-body").textContent = "检查中…";
      const res = await adminFetch("/api/admin/version?check=1");
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "检查失败");
      versionInfoCache = data;
      renderVersionBadge(data, { highlightUpdate: true });
      renderVersionModalBody(data);
      if (showToastOnSuccess) showToast("已检查更新", "success");
    }

    async function openVersionModal() {
      $("version-modal").classList.add("show");
      $("version-modal-body").textContent = "加载中…";
      try {
        const res = await adminFetch("/api/admin/version");
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "加载失败");
        versionInfoCache = data;
        renderVersionModalBody(data);
      } catch (error) {
        $("version-modal-body").textContent = error.message || "加载失败";
      }
    }

    async function runDatabaseBackup() {
      try {
        const res = await adminFetch("/api/admin/database/backup", { method: "POST", body: "{}" });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "备份失败");
        showToast(`备份成功: ${(data.path || "").split(/[/\\]/).pop()}`, "success");
        await refreshVersionModal(false);
      } catch (error) {
        showToast(error.message || "备份失败", "error");
      }
    }

    let updatePollTimer = null;

    function setUpdateProgress(percent, label) {
      const wrap = $("version-progress-wrap");
      const bar = $("version-progress-bar");
      const text = $("version-progress-label");
      if (wrap) wrap.hidden = false;
      if (bar) bar.style.width = `${Math.max(0, Math.min(100, Number(percent) || 0))}%`;
      if (text) text.textContent = label || "";
    }

    function stopUpdatePoll() {
      if (updatePollTimer) {
        clearInterval(updatePollTimer);
        updatePollTimer = null;
      }
    }

    function renderUpdateStatus(data) {
      const logEl = $("version-update-log");
      setUpdateProgress(data.progress ?? 0, data.message || "更新中…");
      if (logEl) {
        logEl.hidden = false;
        logEl.textContent = data.log || logEl.textContent || "";
        logEl.scrollTop = logEl.scrollHeight;
      }
    }

    async function waitServiceHealth({ maxAttempts = 90, intervalMs = 2000 } = {}) {
      for (let i = 0; i < maxAttempts; i += 1) {
        try {
          const res = await fetch("/api/admin/health");
          const data = await readAdminJson(res, "健康检查失败");
          if (res.ok && data.ok) return data;
        } catch (_) {
          /* 重建期间 502/连接失败属正常 */
        }
        setUpdateProgress(
          Math.min(99, 92 + Math.floor((i / maxAttempts) * 7)),
          `服务重启中，请稍候…（${i + 1}/${maxAttempts}，期间可能 502）`
        );
        await new Promise((r) => setTimeout(r, intervalMs));
      }
      throw new Error("服务启动超时，请 SSH 执行: docker compose -p codex ps && docker compose -p codex logs --tail 30");
    }

    async function pollUpdateStatus({ maxRounds = 400 } = {}) {
      let rounds = 0;
      let networkErrors = 0;
      stopUpdatePoll();
      return new Promise((resolve, reject) => {
        const tick = async () => {
          rounds += 1;
          try {
            const res = await adminFetch("/api/admin/update/status");
            const data = await readAdminJson(res, "读取更新状态失败");
            networkErrors = 0;
            renderUpdateStatus(data);
            if (data.state === "success") {
              stopUpdatePoll();
              resolve(data);
              return;
            }
            if (data.state === "failed") {
              stopUpdatePoll();
              reject(new Error(data.error || "更新失败，请查看下方日志"));
              return;
            }
            if (rounds >= maxRounds) {
              stopUpdatePoll();
              reject(new Error("更新超时，请 SSH 查看 data/update-latest.log"));
            }
          } catch (error) {
            networkErrors += 1;
            setUpdateProgress(
              Math.min(95, 55 + networkErrors),
              `服务重启中（暂时无法连接，502 正常）… 请勿刷新关闭`
            );
            if (rounds >= maxRounds) {
              stopUpdatePoll();
              reject(error);
            }
          }
        };
        updatePollTimer = setInterval(() => tick().catch(() => {}), 2000);
        tick().catch(() => {});
      });
    }

    async function runSelfUpdate() {
      if (!versionInfoCache?.updateAvailable) {
        showToast(versionInfoCache?.upToDate ? "已是最新，无需更新" : "当前无法更新", "error");
        return;
      }
      if (!versionInfoCache?.selfUpdateEnabled) {
        showToast("未启用一键更新", "error");
        return;
      }
      const updateBtn = $("version-update-btn");
      const logEl = $("version-update-log");
      if (updateBtn) {
        updateBtn.disabled = true;
        updateBtn.textContent = "更新中…";
      }
      if (logEl) {
        logEl.hidden = false;
        logEl.textContent = "";
      }
      setUpdateProgress(0, "正在启动独立更新容器（不会在本容器内执行更新）…");
      try {
        const res = await adminFetch("/api/admin/update/run", { method: "POST", body: "{}" });
        const data = await readAdminJson(res, "启动更新失败");
        if (!res.ok || !data.ok) {
          if (logEl && data.log) logEl.textContent = data.log;
          throw new Error(data.error || "无法启动更新");
        }
        showToast(data.alreadyRunning ? "更新任务进行中" : "更新已开始", "success", 2000);
        const final = await pollUpdateStatus();
        if (logEl && final.log) logEl.textContent = final.log;
        setUpdateProgress(96, "更新完成，等待服务恢复…");
        await waitServiceHealth();
        setUpdateProgress(100, "更新完成");
        showToast("更新完成，页面已恢复", "success", 4000);
        setTimeout(() => {
          loadVersionBadge().catch(() => {});
          refreshVersionModal(false).catch(() => {});
        }, 2500);
      } catch (error) {
        const msg = String(error?.message || "更新失败");
        showToast(msg, "error", 8000);
        if (logEl) {
          const statusRes = await adminFetch("/api/admin/update/status").catch(() => null);
          const statusData = statusRes ? await statusRes.json().catch(() => ({})) : {};
          logEl.textContent = statusData.log || logEl.textContent || (
            msg + "\n\n（请查看 data/update-latest.log）"
          );
        }
        setUpdateProgress(0, "更新失败");
      } finally {
        stopUpdatePoll();
        if (updateBtn) {
          updateBtn.disabled = false;
          updateBtn.textContent = "一键更新";
        }
      }
    }

    async function deleteCardCore(code) {
      const res = await adminFetch("/api/admin/cards/delete", {
        method: "POST",
        body: JSON.stringify({ code }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "删除失败");
    }

    async function deleteCard(code) {
      if (!await showConfirm({
        title: "删除卡密",
        message: `确定删除卡密 ${code} 吗？`,
        confirmText: "删除",
        danger: true,
      })) return;
      await deleteCardCore(code);
      selectedCardCodes.delete(code);
      await loadDashboard();
    }

    async function deleteSelectedCards() {
      const codes = [...selectedCardCodes];
      if (!codes.length) {
        showToast("请先勾选卡密", "error");
        return;
      }
      if (!await showConfirm({
        title: "批量删除卡密",
        message: `确定删除选中的 ${codes.length} 个卡密吗？`,
        confirmText: "全部删除",
        danger: true,
      })) return;
      let deleted = 0;
      let failed = 0;
      for (const code of codes) {
        try {
          await deleteCardCore(code);
          selectedCardCodes.delete(code);
          deleted += 1;
        } catch (error) {
          failed += 1;
        }
      }
      await loadDashboard();
      showToast(
        failed ? `已删除 ${deleted} 个，失败 ${failed} 个` : `已删除 ${deleted} 个卡密`,
        failed ? "error" : "success",
      );
    }

    async function resetApiKey() {
      if (!await showConfirm({
        title: "重置 API 密钥",
        message: "确定重置对外 API 密钥吗？旧密钥会立即失效，所有正在使用的客户端都需要更新。",
        confirmText: "重置密钥",
        danger: true,
      })) return;
      const res = await adminFetch("/api/admin/settings/reset-api-key", { method: "POST", body: "{}" });
      const data = await readAdminJson(res, "重置 API 密钥失败");
      if (!res.ok) throw new Error(data.error || "重置 API 密钥失败");
      renderApiSettings(data);
      showToast("API 密钥已重置", "success");
      return data;
    }

    async function loginAdmin() {
      $("login-status").textContent = "登录中...";
      const password = $("admin-password").value;
      try {
        const res = await fetch("/api/admin/login", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ password }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "登录失败");
        setToken(data.token);
        persistRememberPassword(password);
        showApp();
        switchTab(activeTab);
        await loadDashboard();
        $("login-status").textContent = "";
      } catch (error) {
        $("login-status").textContent = localizeAdminError(error.message, "登录失败");
        showToast(error.message, "error");
      }
    }

    $("login-btn").addEventListener("click", loginAdmin);
    $("admin-password").addEventListener("keydown", (event) => {
      if (event.key !== "Enter") return;
      event.preventDefault();
      loginAdmin();
    });

    document.querySelectorAll(".nav-tab").forEach((tab) => {
      tab.addEventListener("click", () => switchTab(tab.dataset.tab || "accounts"));
    });

    window.addEventListener("hashchange", () => {
      if (!$("app-panel") || $("app-panel").style.display === "none") return;
      switchTab(readTabFromLocation(), { updateHistory: false });
    });

    $("logout-btn").addEventListener("click", () => {
      setToken("");
      showLogin();
    });

    $("refresh-btn").addEventListener("click", async () => {
      const currentTab = activeTab;
      try {
        await loadDashboard();
        switchTab(currentTab);
        showToast("已刷新", "success");
      } catch (error) {
        switchTab(currentTab);
        showToast(error.message || "刷新失败", "error");
      }
    });

    $("version-btn").addEventListener("click", () => {
      openVersionModal().catch((error) => showToast(error.message || "打开失败", "error"));
    });
    $("version-modal-close").addEventListener("click", closeVersionModal);
    $("version-modal").addEventListener("click", (event) => {
      if (event.target === $("version-modal")) closeVersionModal();
    });

    $("refresh-logs-btn").addEventListener("click", async () => {
      try {
        await loadActivityLogs();
        showToast("日志已刷新", "success");
      } catch (error) {
        showToast(error.message || "刷新失败", "error");
      }
    });

    $("clear-logs-btn").addEventListener("click", async () => {
      if (!await showConfirm({
        title: "清理所有日志",
        message: "确定删除全部运行日志吗？此操作不可恢复。",
        confirmText: "全部清理",
        danger: true,
      })) return;
      try {
        const res = await adminFetch("/api/admin/logs/clear", { method: "POST", body: "{}" });
        const data = await readAdminJson(res, "清理日志失败");
        if (!res.ok) throw new Error(data.error || "清理日志失败");
        logState.page = 1;
        await loadActivityLogs();
        showToast(`已清理 ${data.deleted ?? 0} 条日志`, "success");
      } catch (error) {
        showToast(error.message || "清理日志失败", "error");
      }
    });

    ["log-level-filter", "log-category-filter"].forEach((id) => {
      $(id).addEventListener("change", () => {
        logState.page = 1;
        loadActivityLogs().catch((error) => showToast(error.message || "加载日志失败", "error"));
      });
    });
    ["log-email-filter", "log-action-filter"].forEach((id) => {
      $(id).addEventListener("keydown", (event) => {
        if (event.key !== "Enter") return;
        logState.page = 1;
        loadActivityLogs().catch((error) => showToast(error.message || "加载日志失败", "error"));
      });
    });
    $("log-auto-refresh").addEventListener("change", () => {
      if (activeTab === "logs") startLogsAutoRefresh();
    });
    $("logs-prev").addEventListener("click", async () => {
      if (logState.page <= 1) return;
      logState.page -= 1;
      try {
        await loadActivityLogs();
      } catch (error) {
        showToast(error.message || "加载日志失败", "error");
      }
    });
    $("logs-next").addEventListener("click", async () => {
      logState.page += 1;
      try {
        await loadActivityLogs();
      } catch (error) {
        logState.page = Math.max(1, logState.page - 1);
        showToast(error.message || "加载日志失败", "error");
      }
    });

    document.querySelectorAll(".import-tab[data-import-type]").forEach((tab) => {
      tab.addEventListener("click", () => {
        importAccountType = tab.dataset.importType || "email";
        document.querySelectorAll(".import-tab[data-import-type]").forEach((item) => {
          item.classList.toggle("active", item === tab);
        });
        updateImportPanels();
      });
    });

    document.querySelectorAll("[data-oauth-method]").forEach((tab) => {
      tab.addEventListener("click", () => {
        oauthMethod = tab.dataset.oauthMethod || "manual";
        updateOAuthPanels();
      });
    });

    $("accounts-table").addEventListener("dblclick", (event) => {
      const display = event.target.closest("[data-remark-display]");
      if (display) beginRemarkEdit(display);
    });
    $("accounts-table").addEventListener("keydown", (event) => {
      const input = event.target.closest("[data-remark-input]");
      if (!input) return;
      if (event.key === "Enter") {
        event.preventDefault();
        finishRemarkEdit(input).catch(() => {});
      } else if (event.key === "Escape") {
        const accountId = input.dataset.accountId;
        const display = document.querySelector(`[data-remark-display][data-account-id="${accountId}"]`);
        input.hidden = true;
        if (display) display.hidden = false;
      }
    });
    $("accounts-table").addEventListener("blur", (event) => {
      const input = event.target.closest("[data-remark-input]");
      if (input && !input.hidden) finishRemarkEdit(input).catch(() => {});
    }, true);

    $("import-accounts-btn").addEventListener("click", async () => {
      try {
        const material = $("account-material").value;
        await runImportFast(
          { material, accountType: "email" },
          { clearInputs: () => { $("account-material").value = ""; } },
        );
      } catch (error) {
        showToast(error.message || "导入失败", "error");
      }
    });

    $("oauth-generate-link-btn").addEventListener("click", async () => {
      $("import-status").style.display = "";
      $("import-status").textContent = "生成授权链接中...";
      try {
        const res = await adminFetch("/api/admin/openai/generate-auth-url", { method: "POST", body: "{}" });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "生成失败");
        oauthSession = { sessionId: data.sessionId, state: data.state, authUrl: data.authUrl };
        $("oauth-auth-url").textContent = data.authUrl || "";
        $("oauth-open-link-btn").disabled = !data.authUrl;
        $("oauth-copy-link-btn").disabled = !data.authUrl;
        $("import-status").textContent = "授权链接已生成，请在浏览器完成登录";
        showToast("授权链接已生成", "success");
      } catch (error) {
        $("import-status").textContent = localizeAdminError(error.message, "生成失败");
        showToast(error.message || "生成失败", "error");
      } finally {
        $("import-status").style.display = "none";
      }
    });

    $("oauth-open-link-btn").addEventListener("click", () => {
      if (oauthSession.authUrl) window.open(oauthSession.authUrl, "_blank");
    });

    $("oauth-copy-link-btn").addEventListener("click", async () => {
      const link = oauthSession.authUrl || $("oauth-auth-url").textContent.trim();
      if (!link || link === "尚未生成授权链接") {
        showToast("没有可复制的链接", "error");
        return;
      }
      try {
        await navigator.clipboard.writeText(link);
        showToast("链接已复制", "success");
      } catch (error) {
        showToast("复制失败", "error");
      }
    });

    $("oauth-complete-btn").addEventListener("click", async () => {
      try {
        await importOAuth({
          oauthMethod: "manual",
          sessionId: oauthSession.sessionId,
          state: oauthSession.state,
          authInput: $("oauth-auth-input").value,
        });
        $("oauth-auth-input").value = "";
      } catch (error) {
        showToast(error.message || "授权导入失败", "error");
      }
    });

    $("oauth-import-rt-btn").addEventListener("click", async () => {
      try {
        await importOAuth({ oauthMethod: "rt", material: $("oauth-rt-input").value });
        $("oauth-rt-input").value = "";
      } catch (error) {
        showToast(error.message || "导入失败", "error");
      }
    });

    $("oauth-import-mobile-rt-btn").addEventListener("click", async () => {
      try {
        await importOAuth({ oauthMethod: "mobile_rt", material: $("oauth-mobile-rt-input").value });
        $("oauth-mobile-rt-input").value = "";
      } catch (error) {
        showToast(error.message || "导入失败", "error");
      }
    });

    $("oauth-import-codex-btn").addEventListener("click", async () => {
      try {
        await importOAuth({ oauthMethod: "codex_json", material: $("oauth-codex-input").value });
        $("oauth-codex-input").value = "";
      } catch (error) {
        showToast(error.message || "导入失败", "error");
      }
    });

    $("save-settings-btn").addEventListener("click", async () => {
      $("settings-status").textContent = "保存中...";
      try {
        await saveSettings();
        $("settings-status").textContent = "";
        showToast("设置已保存", "success");
      } catch (error) {
        $("settings-status").textContent = localizeAdminError(error.message, "保存失败");
        showToast(error.message || "保存失败", "error");
      }
    });

    $("auto-test-now-btn")?.addEventListener("click", () => {
      runAutoTestNow().catch((error) => showToast(error.message || "启动测试失败", "error"));
    });

    $("test-proxy-btn").addEventListener("click", () => {
      testProxyPool().catch((error) => showToast(error.message || "代理测试失败", "error"));
    });

    $("copy-api-key-btn").addEventListener("click", async () => {
      const key = $("setting-api-key")?.value?.trim() || "";
      if (!key) {
        showToast("暂无 API 密钥", "error");
        return;
      }
      try {
        await navigator.clipboard.writeText(key);
        showToast("API 密钥已复制", "success");
      } catch (error) {
        showToast("复制失败", "error");
      }
    });

    $("reset-api-key-btn").addEventListener("click", async () => {
      try {
        await resetApiKey();
      } catch (error) {
        showToast(error.message || "重置 API 密钥失败", "error");
      }
    });

    $("reset-password-btn").addEventListener("click", async () => {
      if (!await showConfirm({
        title: "恢复默认密码",
        message: "确定恢复为默认后台密码吗？恢复后将使用 admin123（或环境变量 ADMIN_PASSWORD）。",
        confirmText: "恢复默认",
        danger: true,
      })) return;
      $("settings-status").textContent = "恢复中...";
      try {
        await saveSettings({ clearPassword: true });
        $("settings-status").textContent = "";
        showToast("已恢复默认密码", "success");
      } catch (error) {
        $("settings-status").textContent = localizeAdminError(error.message, "恢复失败");
        showToast(error.message || "恢复失败", "error");
      }
    });

    $("create-cards-btn").addEventListener("click", async () => {
      $("cards-status").textContent = "生成中...";
      try {
        const res = await adminFetch("/api/admin/cards/create", {
          method: "POST",
          body: JSON.stringify({ count: Number($("card-count").value || 1), poolType: listState.cards.poolType || "pp" }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "生成失败");
        $("cards-output").textContent = (data.codes || []).join("\n");
        $("cards-status").textContent = `已生成 ${data.count} 个卡密`;
        await loadDashboard();
        showToast(`已生成 ${data.count} 个卡密`, "success");
      } catch (error) {
        $("cards-status").textContent = localizeAdminError(error.message, "生成失败");
        showToast(error.message || "生成失败", "error");
      }
    });

    $("copy-cards-btn").addEventListener("click", async () => {
      const text = $("cards-output").textContent.trim();
      if (!text || text === "生成后会显示在这里") {
        showToast("没有可复制的卡密", "error");
        return;
      }
      await navigator.clipboard.writeText(text);
      $("cards-status").textContent = "卡密已复制";
      showToast("卡密已复制", "success");
    });

    $("cards-page-size").addEventListener("change", async (event) => {
      listState.cards.pageSize = Number(event.target.value);
      localStorage.setItem(CARDS_PAGE_SIZE_KEY, String(listState.cards.pageSize));
      listState.cards.page = 1;
      try { await loadCards(); } catch (error) { showToast(error.message, "error"); }
    });

    $("accounts-page-size").addEventListener("change", async (event) => {
      listState.accounts.pageSize = Number(event.target.value);
      localStorage.setItem(ACCOUNTS_PAGE_SIZE_KEY, String(listState.accounts.pageSize));
      listState.accounts.page = 1;
      try { await loadAccounts(); } catch (error) { showToast(error.message, "error"); }
    });

    document.querySelectorAll(".account-group-tabs [data-account-group]").forEach((tab) => {
      tab.addEventListener("click", async () => {
        listState.accounts.group = tab.dataset.accountGroup || "all";
        listState.accounts.page = 1;
        localStorage.setItem(ACCOUNT_GROUP_KEY, listState.accounts.group);
        updateAccountGroupTabs();
        try { await loadAccounts(); } catch (error) { showToast(error.message, "error"); }
      });
    });

    document.querySelectorAll(".card-pool-tabs").forEach((group) => {
      group.addEventListener("click", async (event) => {
        const tab = event.target.closest("[data-card-pool]");
        if (!tab) return;
        listState.cards.poolType = tab.dataset.cardPool || "pp";
        localStorage.setItem(CARD_POOL_KEY, listState.cards.poolType);
        listState.cards.page = 1;
        updateCardsPoolUi();
        try {
          await loadCards();
          await loadStats();
        } catch (error) {
          showToast(error.message || "加载卡密失败", "error");
        }
      });
    });

    $("cards-prev").addEventListener("click", async () => {
      if (listState.cards.page <= 1) return;
      listState.cards.page -= 1;
      try { await loadCards(); } catch (error) { showToast(error.message, "error"); }
    });

    $("cards-next").addEventListener("click", async () => {
      listState.cards.page += 1;
      try { await loadCards(); } catch (error) { showToast(error.message, "error"); }
    });

    $("accounts-prev").addEventListener("click", async () => {
      if (listState.accounts.page <= 1) return;
      listState.accounts.page -= 1;
      try { await loadAccounts(); } catch (error) { showToast(error.message, "error"); }
    });

    $("accounts-next").addEventListener("click", async () => {
      listState.accounts.page += 1;
      try { await loadAccounts(); } catch (error) { showToast(error.message, "error"); }
    });

    $("cards-table").addEventListener("click", async (event) => {
      const target = event.target;

      if (target.classList.contains("card-check")) {
        event.stopPropagation();
        const code = target.dataset.cardCode;
        if (!code) return;
        if (target.checked) selectedCardCodes.add(code);
        else selectedCardCodes.delete(code);
        renderCards({ items: listState.lastCards || [], ...(listState.cardsMeta || {}) });
        return;
      }

      const code = target.dataset.deleteCard;
      if (code) {
        event.stopPropagation();
        try {
          await deleteCard(code);
          selectedCardCodes.delete(code);
          showToast("卡密已删除", "success");
        } catch (error) {
          showToast(error.message, "error");
        }
        return;
      }

      const rowEl = target.closest("tr.card-row");
      if (!rowEl || isInteractiveTarget(target)) return;
      selectCardRow(rowEl.dataset.cardRow);
    });

    $("accounts-delete-selected").addEventListener("click", async () => {
      try {
        await deleteSelectedAccounts();
      } catch (error) {
        showToast(error.message || "删除失败", "error");
      }
    });

    $("cards-delete-selected").addEventListener("click", async () => {
      try {
        await deleteSelectedCards();
      } catch (error) {
        showToast(error.message || "删除失败", "error");
      }
    });

    $("accounts-select-all").addEventListener("change", (event) => {
      const checked = event.target.checked;
      const rows = listState.lastAccounts || [];
      rows.forEach((row) => {
        if (checked) selectedAccountIds.add(row.id);
        else selectedAccountIds.delete(row.id);
      });
      if (checked && rows[0]) selectedAccountId = rows[0].id;
      if (!checked) selectedAccountId = "";
      renderAccounts({ items: rows, ...(listState.accountsMeta || {}) });
    });

    $("cards-select-all").addEventListener("change", (event) => {
      const checked = event.target.checked;
      const rows = listState.lastCards || [];
      rows.forEach((row) => {
        if (checked) selectedCardCodes.add(row.code);
        else selectedCardCodes.delete(row.code);
      });
      renderCards({ items: rows, ...(listState.cardsMeta || {}) });
    });

    $("accounts-table").addEventListener("change", async (event) => {
      const target = event.target;
      if (!target.classList.contains("inline-test-proxy")) return;
      const accountId = target.dataset.accountId;
      if (!accountId) return;
      try {
        await runAccountProxyUpdate(accountId, target.value);
      } catch (error) {
        showToast(error.message || "更新代理失败", "error");
        await loadAccounts();
      }
    });

    $("accounts-table").addEventListener("click", async (event) => {
      const target = event.target;

      const copyEmailEl = target.closest(".account-email-copy");
      if (copyEmailEl) {
        event.stopPropagation();
        try {
          await copyAccountEmail(copyEmailEl.dataset.copyEmail || copyEmailEl.textContent);
        } catch (error) {
          showToast(error.message || "复制失败", "error");
        }
        return;
      }

      if (target.classList.contains("account-check")) {
        event.stopPropagation();
        const accountId = target.dataset.accountId;
        if (!accountId) return;
        if (target.checked) {
          selectedAccountIds.add(accountId);
          selectedAccountId = accountId;
        } else {
          selectedAccountIds.delete(accountId);
          if (selectedAccountId === accountId) selectedAccountId = "";
        }
        renderAccounts({ items: listState.lastAccounts || [], ...(listState.accountsMeta || {}) });
        return;
      }

      if (target.dataset.deleteAccount) {
        event.stopPropagation();
        const row = (listState.lastAccounts || []).find((item) => item.id === target.dataset.deleteAccount);
        try {
          await deleteAccount(target.dataset.deleteAccount, row?.email || target.dataset.deleteAccount);
          selectedAccountIds.delete(target.dataset.deleteAccount);
          if (selectedAccountId === target.dataset.deleteAccount) selectedAccountId = "";
          showToast("账号已删除", "success");
        } catch (error) {
          showToast(error.message || "删除失败", "error");
        }
        return;
      }

      if (target.dataset.queryQuota) {
        try {
          await runAccountQuota(target.dataset.queryQuota);
        } catch (error) {
          showToast(error.message || "查询额度失败", "error");
        }
        return;
      }

      const accountId = target.dataset.accountId;
      if (accountId) {
        if (target.classList.contains("inline-priority-sale-btn")) {
          const currentlyOn = target.dataset.prioritySale === "1";
          try {
            await toggleAccountPrioritySale(accountId, !currentlyOn);
            showToast(currentlyOn ? "已取消优先出售" : "已设为优先出售，下次取号优先", "success");
            renderAccounts({ items: listState.lastAccounts || [], ...(listState.accountsMeta || {}) });
          } catch (error) {
            showToast(error.message || "操作失败", "error");
          }
          return;
        }

        if (target.classList.contains("inline-close-test-btn")) {
          testingAccount = null;
          reauthOpenAccountId = "";
          mailboxOpenAccountId = "";
          delete reauthModes[accountId];
          sessionStorage.removeItem(EXPANDED_ACCOUNT_KEY);
          renderAccounts({ items: listState.lastAccounts || [], ...(listState.accountsMeta || {}) });
          return;
        }

        if (target.classList.contains("inline-open-mailbox-btn")) {
          mailboxOpenAccountId = accountId;
          reauthOpenAccountId = "";
          renderAccounts({ items: listState.lastAccounts || [], ...(listState.accountsMeta || {}) });
          return;
        }

        if (target.classList.contains("inline-mailbox-cancel-btn")) {
          mailboxOpenAccountId = "";
          renderAccounts({ items: listState.lastAccounts || [], ...(listState.accountsMeta || {}) });
          return;
        }

        if (target.classList.contains("inline-mailbox-save-btn")) {
          try {
            await runAccountMailboxLink(accountId);
          } catch (error) {
            showToast(error.message || "绑定邮箱失败", "error");
          }
          return;
        }

        if (target.classList.contains("inline-open-oauth-btn")) {
          reauthOpenAccountId = accountId;
          mailboxOpenAccountId = "";
          reauthModes[accountId] = "optional";
          renderAccounts({ items: listState.lastAccounts || [], ...(listState.accountsMeta || {}) });
          return;
        }

        if (target.classList.contains("inline-open-reauth-btn")) {
          reauthOpenAccountId = accountId;
          mailboxOpenAccountId = "";
          reauthModes[accountId] = "recovery";
          renderAccounts({ items: listState.lastAccounts || [], ...(listState.accountsMeta || {}) });
          return;
        }

        if (target.classList.contains("inline-reauth-cancel-btn")) {
          reauthOpenAccountId = "";
          delete reauthSessions[accountId];
          delete reauthModes[accountId];
          renderAccounts({ items: listState.lastAccounts || [], ...(listState.accountsMeta || {}) });
          return;
        }

        if (target.classList.contains("inline-reauth-link-btn")) {
          try {
            await generateReauthLink(accountId);
          } catch (error) {
            showToast(error.message || "生成授权链接失败", "error");
          }
          return;
        }

        if (target.classList.contains("inline-reauth-open-btn")) {
          const link = reauthSessions[accountId]?.authUrl;
          if (link) window.open(link, "_blank");
          return;
        }

        if (target.classList.contains("inline-reauth-copy-btn")) {
          const link = reauthSessions[accountId]?.authUrl || document.querySelector(`.inline-reauth-url[data-account-id="${accountId}"]`)?.textContent?.trim();
          if (!link || link === "尚未生成授权链接") {
            showToast("请先生成授权链接", "error");
            return;
          }
          try {
            await navigator.clipboard.writeText(link);
            showToast("链接已复制", "success");
          } catch (error) {
            showToast("复制失败", "error");
          }
          return;
        }

        if (target.classList.contains("inline-reauth-complete-btn")) {
          const optional = (reauthModes[accountId] || target.dataset.reauthMode) === "optional";
          try {
            await runAccountReauth(accountId, { optional });
          } catch (error) {
            showToast(error.message || (optional ? "OAuth 授权失败" : "重新授权失败"), "error");
          }
          return;
        }

        if (target.classList.contains("inline-run-test-btn")) {
          const model = document.querySelector(`.inline-test-model[data-account-id="${accountId}"]`)?.value;
          const message = document.querySelector(`.inline-test-message[data-account-id="${accountId}"]`)?.value;
          try {
            await runAccountTest(accountId, model, message);
          } catch (error) {
            const resultBox = document.querySelector(`.inline-test-result[data-account-id="${accountId}"]`);
            if (resultBox) resultBox.textContent = formatAdminErrorForPanel(error, error.apiData);
            showToast(localizeAdminError(error.message) || "测试失败", "error", 8000);
          }
          return;
        }

        if (target.classList.contains("inline-login-btn")) {
          try {
            await runAccountLogin(accountId);
          } catch (error) {
            const resultBox = document.querySelector(`.inline-test-result[data-account-id="${accountId}"]`);
            if (resultBox) resultBox.textContent = formatAdminErrorForPanel(error, error.apiData);
            showToast(localizeAdminError(error.message) || "重新登录失败", "error", 8000);
          }
          return;
        }

        if (target.classList.contains("inline-query-quota-btn")) {
          try {
            await runAccountQuota(accountId);
          } catch (error) {
            showToast(error.message || "查询额度失败", "error");
          }
          return;
        }

        if (target.classList.contains("inline-read-mailbox-btn")) {
          if (mailboxBusyAccountId) return;
          try {
            await runAccountMailboxOtp(accountId);
          } catch (_error) {}
          return;
        }

        if (target.classList.contains("inline-export-btn")) {
          try {
            await runAccountExport(accountId);
          } catch (error) {
            showToast(error.message || "导出失败", "error", 5000);
          }
          return;
        }

        return;
      }

      const rowEl = target.closest("tr.account-row");
      if (!rowEl || isInteractiveTarget(target)) return;
      clearTimeout(accountRowClickTimer);
      accountRowClickTimer = setTimeout(() => {
        selectAccountRow(rowEl.dataset.accountRow);
      }, 220);
    });

    $("accounts-table").addEventListener("dblclick", (event) => {
      const target = event.target;
      if (isInteractiveTarget(target)) return;
      const rowEl = target.closest("tr.account-row");
      if (!rowEl) return;
      clearTimeout(accountRowClickTimer);
      const row = (listState.lastAccounts || []).find((item) => item.id === rowEl.dataset.accountRow);
      if (!row) return;
      selectedAccountId = row.id;
      selectedAccountIds.add(row.id);
      toggleAccountExpand(row);
    });

    initAutoTestIntervalSelect();
    loadSavedLogin();
    if (token()) {
      showApp();
      if (isAccountsTab(activeTab)) {
        listState.accounts.poolType = accountTabPoolType(activeTab);
      }
      switchTab(activeTab, { updateHistory: false });
      updateImportPanels();
      updateCardsPoolUi();
      loadDashboard().catch(showLogin);
    } else {
      showLogin();
    }
  </script>
</body>
</html>

"""
