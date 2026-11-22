/* ==========================================================================
   BrandGuard AI — Frontend SPA Controller (Zero Dependencies)
   ========================================================================== */

(() => {
  "use strict";

  const TOKEN_KEY = "brandguard_auth_token";
  const MAX_FILE_BYTES = 5 * 1024 * 1024; // 5MB
  const ALLOWED_IMAGE_EXTS = [".png", ".jpg", ".jpeg", ".webp"];
  const ALLOWED_DOC_EXTS = [".pdf", ".docx", ".txt"];
  const RING_CIRCUMFERENCE = 2 * Math.PI * 40; // r=40

  const SAMPLE_DRAFTS = {
    roi: "Guaranteed to make you a millionaire overnight! Buy now customers!!!",
    casual: "Hey guys!! Our crazy insane software is super cheap and totally destroys competitors!",
    compliant: "Our platform helps enterprise clients streamline governance workflows with measurable operational clarity.",
  };

  // Application state
  let authToken = localStorage.getItem(TOKEN_KEY) || "";
  let selectedImageFile = null;
  let selectedDocFile = null;
  let lastRewriteText = "";

  // DOM Shortcuts
  const $ = (id) => document.getElementById(id);

  // ------------------------------------------------------------------------
  // Utilities
  // ------------------------------------------------------------------------
  function setButtonLoading(btn, isLoading) {
    if (!btn) return;
    btn.disabled = isLoading;
    const spinner = btn.querySelector(".spinner");
    if (spinner) spinner.classList.toggle("hidden", !isLoading);
  }

  function showBanner(el, message, type = "error") {
    if (!el) return;
    el.textContent = message;
    el.className = `inline-banner inline-banner--${type}`;
    el.classList.remove("hidden");
  }

  function hideBanner(el) {
    if (!el) return;
    el.classList.add("hidden");
    el.textContent = "";
  }

  function getExtension(filename) {
    const idx = (filename || "").lastIndexOf(".");
    return idx >= 0 ? filename.slice(idx).toLowerCase() : "";
  }

  function statusColor(status) {
    if (status === "approved") return "#1D7F42";
    if (status === "flagged") return "#B25E09";
    return "#D70015";
  }

  function statusLabel(status) {
    if (status === "approved") return "Approved";
    if (status === "flagged") return "Flagged";
    return "Violation";
  }

  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str == null ? "" : String(str);
    return div.innerHTML;
  }

  async function apiFetch(url, options = {}) {
    const headers = new Headers(options.headers || {});
    if (authToken) {
      headers.set("Authorization", `Bearer ${authToken}`);
    }
    const resp = await fetch(url, { ...options, headers });
    let data = null;
    try {
      data = await resp.json();
    } catch {
      data = null;
    }
    if (!resp.ok) {
      const detail = (data && data.detail) || `Request failed (${resp.status})`;
      const err = new Error(detail);
      err.status = resp.status;
      throw err;
    }
    return data;
  }

  // Slow-request helper (> 5 seconds)
  function startSlowTimer(noteEl) {
    if (noteEl) noteEl.classList.add("hidden");
    return window.setTimeout(() => {
      if (noteEl) noteEl.classList.remove("hidden");
    }, 5000);
  }

  function clearSlowTimer(timerId, noteEl) {
    window.clearTimeout(timerId);
    if (noteEl) noteEl.classList.add("hidden");
  }

  // ------------------------------------------------------------------------
  // Auth Flow
  // ------------------------------------------------------------------------
  function showAuthScreen() {
    $("auth-screen").classList.remove("hidden");
    $("app-shell").classList.add("hidden");
  }

  function showWorkspace() {
    $("auth-screen").classList.add("hidden");
    $("app-shell").classList.remove("hidden");
  }

  async function performLogin(username, password, triggerBtn) {
    hideBanner($("login-error"));
    setButtonLoading(triggerBtn, true);
    try {
      const res = await apiFetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      authToken = res.token;
      localStorage.setItem(TOKEN_KEY, authToken);
      showWorkspace();
      await bootstrapWorkspace();
    } catch (err) {
      showBanner($("login-error"), err.message || "Unable to sign in.", "error");
    } finally {
      setButtonLoading(triggerBtn, false);
    }
  }

  async function checkExistingSession() {
    if (!authToken) {
      showAuthScreen();
      return;
    }
    try {
      await apiFetch("/api/auth/me");
      showWorkspace();
      await bootstrapWorkspace();
    } catch {
      authToken = "";
      localStorage.removeItem(TOKEN_KEY);
      showAuthScreen();
    }
  }

  function signOut() {
    authToken = "";
    localStorage.removeItem(TOKEN_KEY);
    $("login-username").value = "";
    $("login-password").value = "";
    hideBanner($("login-error"));
    showAuthScreen();
  }

  // ------------------------------------------------------------------------
  // Workspace Bootstrap & Tab Switching
  // ------------------------------------------------------------------------
  async function bootstrapWorkspace() {
    await Promise.all([loadHealthStatus(), loadGuidelines()]);
  }

  async function loadHealthStatus() {
    try {
      const health = await apiFetch("/api/health");
      $("ai-config-banner").classList.toggle("hidden", Boolean(health.ai_configured));
      updateRuleCountUI(health.guidelines_count);
    } catch {
      // Non-fatal
    }
  }

  function updateRuleCountUI(count) {
    const n = Number(count) || 0;
    $("rule-count-text").textContent = `${n} Active ${n === 1 ? "Rule" : "Rules"}`;
    $("rules-list-count").textContent = `${n} ${n === 1 ? "rule" : "rules"}`;
  }

  function switchTab(tabName) {
    const tabs = ["text", "visual", "rules"];
    tabs.forEach((name) => {
      const btn = $(`tab-btn-${name}`);
      const panel = $(`panel-${name}`);
      const isActive = name === tabName;
      btn.classList.toggle("active", isActive);
      btn.setAttribute("aria-selected", String(isActive));
      panel.classList.toggle("active", isActive);
    });
  }

  // ------------------------------------------------------------------------
  // Score Ring & Status Renderer (Shared by Text & Visual Tabs)
  // ------------------------------------------------------------------------
  function renderScoreVisuals(prefix, score, status) {
    const clamped = Math.max(0, Math.min(100, Number(score) || 0));
    const color = statusColor(status);

    const numEl = $(`${prefix}-score-number`);
    const arcEl = $(`${prefix}-score-arc`);
    const barEl = $(`${prefix}-score-bar`);
    const pillEl = $(`${prefix}-status-pill`);

    numEl.textContent = String(clamped);
    arcEl.style.stroke = color;
    arcEl.style.strokeDasharray = String(RING_CIRCUMFERENCE);
    // Reset then animate on next frame
    arcEl.style.strokeDashoffset = String(RING_CIRCUMFERENCE);
    barEl.style.width = "0%";
    barEl.style.background = color;

    requestAnimationFrame(() => {
      const offset = RING_CIRCUMFERENCE * (1 - clamped / 100);
      arcEl.style.strokeDashoffset = String(offset);
      barEl.style.width = `${clamped}%`;
    });

    pillEl.textContent = statusLabel(status);
    pillEl.className = `status-pill status-pill--${status}`;
  }

  function renderBrokenRules(containerEl, brokenRules) {
    containerEl.innerHTML = "";
    if (!brokenRules || brokenRules.length === 0) {
      containerEl.innerHTML =
        '<div class="rule-finding-card rule-finding-card--clean">No brand guideline violations detected.</div>';
      return;
    }
    brokenRules.forEach((rule) => {
      const div = document.createElement("div");
      div.className = "rule-finding-card rule-finding-card--violation";
      div.textContent = rule;
      containerEl.appendChild(div);
    });
  }

  function renderBulletList(listEl, items, emptyText) {
    listEl.innerHTML = "";
    if (!items || items.length === 0) {
      const li = document.createElement("li");
      li.className = "meta-text";
      li.textContent = emptyText;
      listEl.appendChild(li);
      return;
    }
    items.forEach((item) => {
      const li = document.createElement("li");
      li.textContent = item;
      listEl.appendChild(li);
    });
  }

  // ------------------------------------------------------------------------
  // TAB 1: Text Audit
  // ------------------------------------------------------------------------
  function updateCharCount() {
    const len = $("text-audit-input").value.length;
    $("text-char-count").textContent = `${len} ${len === 1 ? "character" : "characters"}`;
  }

  async function runTextAudit() {
    const inputEl = $("text-audit-input");
    const errEl = $("text-audit-error");
    const btn = $("text-audit-submit");
    const slowEl = $("text-slow-note");

    hideBanner(errEl);
    const text = inputEl.value.trim();
    if (!text) {
      showBanner(errEl, "Please enter marketing copy to audit before submitting.", "error");
      inputEl.focus();
      return;
    }

    setButtonLoading(btn, true);
    const slowTimer = startSlowTimer(slowEl);

    try {
      const result = await apiFetch("/api/review", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });

      $("text-results-empty").classList.add("hidden");
      $("text-results-content").classList.remove("hidden");

      const checkedEl = $("text-rules-checked");
      checkedEl.textContent = `${result.guidelines_checked} guidelines checked`;
      checkedEl.classList.remove("hidden");

      renderScoreVisuals("text", result.score, result.status);
      $("text-explanation").textContent = result.explanation || "";
      renderBrokenRules($("text-broken-rules"), result.broken_rules);

      lastRewriteText = result.suggestion || "";
      $("text-suggestion-box").textContent = lastRewriteText;
      $("copy-rewrite-btn").textContent = "Copy Compliant Rewrite";
    } catch (err) {
      showBanner(errEl, err.message || "Text audit failed.", "error");
    } finally {
      clearSlowTimer(slowTimer, slowEl);
      setButtonLoading(btn, false);
    }
  }

  async function copyRewrite() {
    if (!lastRewriteText) return;
    const btn = $("copy-rewrite-btn");
    try {
      await navigator.clipboard.writeText(lastRewriteText);
    } catch {
      const tmp = document.createElement("textarea");
      tmp.value = lastRewriteText;
      document.body.appendChild(tmp);
      tmp.select();
      document.execCommand("copy");
      document.body.removeChild(tmp);
    }
    btn.textContent = "Copied!";
    window.setTimeout(() => {
      btn.textContent = "Copy Compliant Rewrite";
    }, 1800);
  }

  // ------------------------------------------------------------------------
  // TAB 2: Visual Audit
  // ------------------------------------------------------------------------
  function setSelectedImage(file) {
    hideBanner($("visual-audit-error"));
    if (!file) {
      selectedImageFile = null;
      $("image-preview").src = "";
      $("image-preview-wrap").classList.add("hidden");
      $("dropzone-placeholder").classList.remove("hidden");
      $("image-file-input").value = "";
      return;
    }

    const ext = getExtension(file.name);
    if (!ALLOWED_IMAGE_EXTS.includes(ext)) {
      showBanner(
        $("visual-audit-error"),
        "Unsupported image format. Please select a PNG, JPG, JPEG, or WEBP file.",
        "error"
      );
      return;
    }

    if (file.size > MAX_FILE_BYTES) {
      showBanner(
        $("visual-audit-error"),
        "Image exceeds the 5MB maximum size limit.",
        "error"
      );
      return;
    }

    selectedImageFile = file;
    const objectUrl = URL.createObjectURL(file);
    $("image-preview").src = objectUrl;
    $("image-file-name").textContent = `${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
    $("dropzone-placeholder").classList.add("hidden");
    $("image-preview-wrap").classList.remove("hidden");
  }

  async function loadSampleImage(filename, caption) {
    hideBanner($("visual-audit-error"));
    try {
      const resp = await fetch(`/api/samples/images/${encodeURIComponent(filename)}`);
      if (!resp.ok) throw new Error("Failed to load sample image.");
      const blob = await resp.blob();
      const file = new File([blob], filename, { type: "image/png" });
      setSelectedImage(file);
      if (caption) {
        $("visual-caption-input").value = caption;
      }
    } catch (err) {
      showBanner($("visual-audit-error"), err.message || "Could not load sample creative.", "error");
    }
  }

  async function runVisualAudit() {
    const errEl = $("visual-audit-error");
    const btn = $("visual-audit-submit");
    const slowEl = $("visual-slow-note");

    hideBanner(errEl);
    if (!selectedImageFile) {
      showBanner(
        errEl,
        "Please upload an image or click one of the sample creatives first.",
        "error"
      );
      return;
    }

    setButtonLoading(btn, true);
    const slowTimer = startSlowTimer(slowEl);

    try {
      const formData = new FormData();
      formData.append("file", selectedImageFile);
      const caption = $("visual-caption-input").value.trim();
      if (caption) formData.append("caption", caption);

      const result = await apiFetch("/api/review/image", {
        method: "POST",
        body: formData,
      });

      $("visual-results-empty").classList.add("hidden");
      $("visual-results-content").classList.remove("hidden");

      const checkedEl = $("visual-rules-checked");
      if (result.guidelines_checked != null) {
        checkedEl.textContent = `${result.guidelines_checked} guidelines checked`;
        checkedEl.classList.remove("hidden");
      }

      renderScoreVisuals("visual", result.score, result.status);
      $("visual-explanation").textContent = result.explanation || "";
      renderBrokenRules($("visual-broken-rules"), result.broken_rules);
      renderBulletList(
        $("visual-findings-list"),
        result.visual_findings,
        "No visual anomalies noted."
      );
      renderBulletList(
        $("visual-text-findings-list"),
        result.text_in_image_findings,
        "No embedded text issues detected."
      );
      renderBulletList(
        $("visual-fixes-list"),
        result.actionable_fixes,
        "No revisions required — asset is ready to publish."
      );
    } catch (err) {
      showBanner(errEl, err.message || "Visual audit failed.", "error");
    } finally {
      clearSlowTimer(slowTimer, slowEl);
      setButtonLoading(btn, false);
    }
  }

  // ------------------------------------------------------------------------
  // TAB 3: Brand Rulebook (Dynamic RAG Updater)
  // ------------------------------------------------------------------------
  async function loadGuidelines() {
    try {
      const data = await apiFetch("/api/guidelines");
      const rules = data.guidelines || [];
      updateRuleCountUI(data.count);
      renderGuidelinesList(rules);
    } catch (err) {
      showBanner($("rules-banner"), err.message || "Could not load guidelines.", "error");
    }
  }

  function renderGuidelinesList(rules) {
    const container = $("rules-list");
    container.innerHTML = "";
    if (!rules.length) {
      container.innerHTML =
        '<div class="empty-state"><p class="empty-title">No active rules</p><p class="empty-subtitle">Add a custom rule, upload a document, or reset to enterprise defaults.</p></div>';
      return;
    }

    rules.forEach((rule) => {
      const card = document.createElement("article");
      card.className = "rule-item";
      card.innerHTML = `
        <div class="rule-item-main">
          <div class="rule-item-header">
            <h4 class="rule-item-title">${escapeHtml(rule.title)}</h4>
            <span class="source-badge">${escapeHtml(rule.source || "manual")}</span>
          </div>
          <p class="rule-item-content">${escapeHtml(rule.content)}</p>
        </div>
        <button type="button" class="btn btn-danger-ghost" data-delete-id="${escapeHtml(rule.id)}">Delete</button>
      `;
      container.appendChild(card);
    });
  }

  async function handleAddRule(evt) {
    evt.preventDefault();
    const banner = $("rules-banner");
    const btn = $("add-rule-submit");
    hideBanner(banner);

    const title = $("rule-title-input").value.trim();
    const content = $("rule-content-input").value.trim();
    if (!title || !content) {
      showBanner(banner, "Please provide both a rule title and policy statement.", "error");
      return;
    }

    setButtonLoading(btn, true);
    try {
      await apiFetch("/api/guidelines/text", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title, content }),
      });
      $("rule-title-input").value = "";
      $("rule-content-input").value = "";
      showBanner(banner, `Added rule "${title}". Active on your very next audit.`, "success");
      await loadGuidelines();
    } catch (err) {
      showBanner(banner, err.message || "Failed to add guideline.", "error");
    } finally {
      setButtonLoading(btn, false);
    }
  }

  async function handleAddSampleRule() {
    const banner = $("rules-banner");
    const btn = $("add-sample-rule-btn");
    hideBanner(banner);
    setButtonLoading(btn, true);
    try {
      await apiFetch("/api/guidelines/text", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: "Premium Pricing Terminology",
          content:
            'Never use words like "cheap", "bargain", or "discount" when describing our products; emphasize enterprise value and predictable investment instead.',
        }),
      });
      showBanner(
        banner,
        'Added sample rule "Premium Pricing Terminology" (blocks "cheap" and "discount").',
        "success"
      );
      await loadGuidelines();
    } catch (err) {
      showBanner(banner, err.message || "Failed to add sample rule.", "error");
    } finally {
      setButtonLoading(btn, false);
    }
  }

  function setSelectedDoc(file) {
    const banner = $("rules-banner");
    hideBanner(banner);
    if (!file) {
      selectedDocFile = null;
      $("doc-file-label").innerHTML = "Drop a rulebook file here, or <span>browse</span>";
      $("doc-file-input").value = "";
      return;
    }

    const ext = getExtension(file.name);
    if (!ALLOWED_DOC_EXTS.includes(ext)) {
      showBanner(banner, "Unsupported file type. Only .pdf, .docx, and .txt files are allowed.", "error");
      return;
    }
    if (file.size > MAX_FILE_BYTES) {
      showBanner(banner, "Document exceeds the 5MB maximum size limit.", "error");
      return;
    }
    selectedDocFile = file;
    $("doc-file-label").textContent = `Selected: ${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
  }

  async function handleUploadRuleDoc(evt) {
    evt.preventDefault();
    const banner = $("rules-banner");
    const btn = $("upload-rule-submit");
    hideBanner(banner);

    if (!selectedDocFile) {
      showBanner(banner, "Please choose a .pdf, .docx, or .txt policy file to upload.", "error");
      return;
    }

    setButtonLoading(btn, true);
    try {
      const formData = new FormData();
      formData.append("file", selectedDocFile);
      const res = await apiFetch("/api/guidelines/upload", {
        method: "POST",
        body: formData,
      });
      setSelectedDoc(null);
      showBanner(
        banner,
        `Indexed ${res.added_count} policy ${res.added_count === 1 ? "chunk" : "chunks"} into ChromaDB.`,
        "success"
      );
      await loadGuidelines();
    } catch (err) {
      showBanner(banner, err.message || "Failed to ingest document.", "error");
    } finally {
      setButtonLoading(btn, false);
    }
  }

  async function handleDeleteRule(ruleId) {
    const banner = $("rules-banner");
    hideBanner(banner);
    try {
      await apiFetch(`/api/guidelines/${encodeURIComponent(ruleId)}`, {
        method: "DELETE",
      });
      showBanner(banner, "Rule removed from active rulebook.", "success");
      await loadGuidelines();
    } catch (err) {
      showBanner(banner, err.message || "Failed to delete rule.", "error");
    }
  }

  async function handleResetRules() {
    const banner = $("rules-banner");
    const btn = $("reset-rules-btn");
    hideBanner(banner);
    setButtonLoading(btn, true);
    try {
      await apiFetch("/api/guidelines/reset", { method: "POST" });
      showBanner(banner, "Rulebook reset to the 4 enterprise default guidelines.", "success");
      await loadGuidelines();
    } catch (err) {
      showBanner(banner, err.message || "Failed to reset guidelines.", "error");
    } finally {
      setButtonLoading(btn, false);
    }
  }

  // ------------------------------------------------------------------------
  // Event Binding
  // ------------------------------------------------------------------------
  function wireDropzone(zoneEl, inputEl, onFileSelected) {
    zoneEl.addEventListener("click", (e) => {
      if (e.target.closest("button")) return;
      inputEl.click();
    });
    zoneEl.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        inputEl.click();
      }
    });
    inputEl.addEventListener("change", () => {
      if (inputEl.files && inputEl.files[0]) {
        onFileSelected(inputEl.files[0]);
      }
    });
    zoneEl.addEventListener("dragover", (e) => {
      e.preventDefault();
      zoneEl.classList.add("drag-over");
    });
    zoneEl.addEventListener("dragleave", () => {
      zoneEl.classList.remove("drag-over");
    });
    zoneEl.addEventListener("drop", (e) => {
      e.preventDefault();
      zoneEl.classList.remove("drag-over");
      if (e.dataTransfer.files && e.dataTransfer.files[0]) {
        onFileSelected(e.dataTransfer.files[0]);
      }
    });
  }

  function init() {
    // Auth events
    $("one-click-demo-btn").addEventListener("click", () => {
      performLogin("test123", "test123", $("one-click-demo-btn"));
    });
    $("login-form").addEventListener("submit", (e) => {
      e.preventDefault();
      performLogin(
        $("login-username").value,
        $("login-password").value,
        $("login-submit-btn")
      );
    });
    $("sign-out-btn").addEventListener("click", signOut);

    // Navigation
    document.querySelectorAll(".segment-btn").forEach((btn) => {
      btn.addEventListener("click", () => switchTab(btn.dataset.tab));
    });
    $("rule-count-pill").addEventListener("click", () => switchTab("rules"));

    // Text Audit
    $("text-audit-input").addEventListener("input", updateCharCount);
    document.querySelectorAll(".sample-pill").forEach((pill) => {
      pill.addEventListener("click", () => {
        const key = pill.dataset.sample;
        if (SAMPLE_DRAFTS[key]) {
          $("text-audit-input").value = SAMPLE_DRAFTS[key];
          updateCharCount();
          hideBanner($("text-audit-error"));
        }
      });
    });
    $("text-clear-btn").addEventListener("click", () => {
      $("text-audit-input").value = "";
      updateCharCount();
      hideBanner($("text-audit-error"));
    });
    $("text-audit-submit").addEventListener("click", runTextAudit);
    $("copy-rewrite-btn").addEventListener("click", copyRewrite);

    // Visual Audit
    wireDropzone($("image-dropzone"), $("image-file-input"), setSelectedImage);
    $("image-remove-btn").addEventListener("click", (e) => {
      e.stopPropagation();
      setSelectedImage(null);
    });
    $("visual-clear-btn").addEventListener("click", () => {
      setSelectedImage(null);
      $("visual-caption-input").value = "";
      hideBanner($("visual-audit-error"));
    });
    document.querySelectorAll(".sample-image-card").forEach((card) => {
      card.addEventListener("click", () => {
        loadSampleImage(card.dataset.sampleImage, card.dataset.sampleCaption);
      });
    });
    $("visual-audit-submit").addEventListener("click", runVisualAudit);

    // Brand Rulebook
    $("add-rule-form").addEventListener("submit", handleAddRule);
    $("add-sample-rule-btn").addEventListener("click", handleAddSampleRule);
    $("reset-rules-btn").addEventListener("click", handleResetRules);
    wireDropzone($("doc-dropzone"), $("doc-file-input"), setSelectedDoc);
    $("upload-rule-form").addEventListener("submit", handleUploadRuleDoc);
    $("rules-list").addEventListener("click", (e) => {
      const delBtn = e.target.closest("[data-delete-id]");
      if (delBtn) {
        handleDeleteRule(delBtn.dataset.deleteId);
      }
    });

    // Verify existing session on page load
    checkExistingSession();
  }

  document.addEventListener("DOMContentLoaded", init);
})();
