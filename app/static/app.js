// Specter AI frontend — vanilla JS, no build step.

const STAGES = [
  { key: "intake", label: "Intake" },
  { key: "match_client", label: "File & Match" },
  { key: "extraction", label: "Extract" },
  { key: "diff", label: "Diff" },
  { key: "risk", label: "Risk" },
  { key: "deadline", label: "Deadline" },
  { key: "notify", label: "Notify" },
];

const AGENT_TALK = {
  intake: "Talking to the Intake & Classification agent…",
  match_client: "Filing under the correct client profile…",
  extraction: "Talking to the Clause Extraction agent…",
  diff: "Talking to the Diff agent — comparing against the prior version…",
  risk: "Talking to the Risk & Ambiguity agent…",
  deadline: "Computing the renewal deadline…",
  notify: "Talking to the Notify/Report agent — drafting summary…",
  queued: "Queued…",
  done: "Verdict ready.",
};

const el = (tag, attrs = {}, children = []) => {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") e.className = v;
    else if (k === "html") e.innerHTML = v;
    else e.setAttribute(k, v);
  }
  for (const c of [].concat(children)) {
    if (c !== null && c !== undefined) e.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
  }
  return e;
};

async function api(path, opts = {}) {
  const res = await fetch(path, { credentials: "same-origin", ...opts });
  if (res.status === 401) {
    showLogin();
    throw new Error("Not authenticated");
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `HTTP ${res.status}`);
  }
  return res.status === 204 ? null : res.json();
}

// ---------------- Auth ----------------

function showLogin() {
  document.getElementById("login-screen").classList.remove("hidden");
  document.getElementById("app").classList.remove("visible");
}

function showApp(displayName) {
  document.getElementById("login-screen").classList.add("hidden");
  document.getElementById("app").classList.add("visible");
  document.getElementById("user-name").textContent = displayName;
  document.getElementById("user-avatar").textContent = displayName.slice(0, 1).toUpperCase();
  loadClients();
}

async function checkAuth() {
  try {
    const me = await fetch("/auth/me", { credentials: "same-origin" });
    if (me.ok) {
      const data = await me.json();
      showApp(data.display_name);
    } else {
      showLogin();
    }
  } catch {
    showLogin();
  }
}

document.getElementById("login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const username = document.getElementById("login-username").value;
  const password = document.getElementById("login-password").value;
  const errorEl = document.getElementById("login-error");
  errorEl.textContent = "";
  try {
    const res = await fetch("/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
      credentials: "same-origin",
    });
    if (!res.ok) throw new Error("Invalid username or password");
    const data = await res.json();
    showApp(data.display_name);
  } catch (err) {
    errorEl.textContent = err.message;
  }
});

document.getElementById("logout-btn").addEventListener("click", async () => {
  await fetch("/auth/logout", { method: "POST", credentials: "same-origin" });
  showLogin();
});

// ---------------- Nav ----------------

document.getElementById("topnav").addEventListener("click", (e) => {
  const btn = e.target.closest("button[data-view]");
  if (!btn) return;
  document.querySelectorAll("#topnav button").forEach((b) => b.classList.remove("active"));
  btn.classList.add("active");
  document.querySelectorAll(".view").forEach((v) => v.classList.remove("active"));
  document.getElementById(`view-${btn.dataset.view}`).classList.add("active");
  if (btn.dataset.view === "history") loadHistory();
  if (btn.dataset.view === "usage") loadUsage();
});

// ---------------- Clients & contracts ----------------

let activeClientEl = null;

async function loadClients() {
  const clients = await api("/clients");
  const list = document.getElementById("client-list");
  list.innerHTML = "";
  if (clients.length === 0) {
    list.appendChild(el("div", { class: "empty-state" }, "No clients yet — upload a contract."));
    return;
  }
  for (const client of clients) {
    const item = el("div", { class: "client-item" }, client.name);
    item.onclick = () => selectClient(client.id, item);
    list.appendChild(item);
  }
}

async function selectClient(clientId, itemEl) {
  document.querySelectorAll(".client-item").forEach((e) => e.classList.remove("active"));
  itemEl.classList.add("active");
  activeClientEl = itemEl;

  const contracts = await api(`/clients/${clientId}/contracts`);
  document.querySelectorAll(".contract-item").forEach((e) => e.remove());

  const sorted = contracts.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
  let anchor = itemEl;
  for (const c of sorted) {
    const label = `${c.contract_type || "Contract"} · ${new Date(c.created_at).toLocaleDateString()}`;
    const item = el("div", { class: "contract-item" }, [
      el("span", { class: `status-dot ${c.status}` }),
      label,
    ]);
    item.dataset.contractId = c.id;
    item.onclick = () => openContract(c.id, item);
    anchor.after(item);
    anchor = item;
  }
  // Switch to workspace view and open the workspace with the upload form
  document.querySelector('#topnav button[data-view="workspace"]').click();
  if (sorted.length) openContract(sorted[0].id, null);
}

function openContract(contractId, itemEl) {
  document.querySelectorAll(".contract-item").forEach((e) => e.classList.remove("active"));
  if (itemEl) itemEl.classList.add("active");
  document.querySelector('#topnav button[data-view="workspace"]').click();
  pollContract(contractId);
}

// ---------------- Pipeline stepper ----------------

function stageIndex(key) {
  return STAGES.findIndex((s) => s.key === key);
}

function computeStepStates(contract) {
  const curKey = contract.current_stage;
  let curIdx;
  if (!curKey || curKey === "queued") curIdx = -1;
  else if (curKey === "done") curIdx = STAGES.length;
  else curIdx = stageIndex(curKey);

  return STAGES.map((s, i) => {
    if (contract.status === "failed" && s.key === curKey) return "failed";
    if (s.key === "diff" && contract.diff == null && curIdx > stageIndex("diff")) return "skipped";
    if (i < curIdx) return "done";
    if (i === curIdx && contract.status === "processing") return "active";
    if (i === curIdx) return "done";
    return "pending";
  });
}

const STEP_ICONS = { done: "✓", failed: "✕", active: "◐", pending: "", skipped: "–" };

function renderStepper(contract) {
  const stepper = document.getElementById("stepper");
  stepper.innerHTML = "";
  const states = computeStepStates(contract);
  STAGES.forEach((s, i) => {
    const state = states[i];
    const node = el("div", { class: "node" }, STEP_ICONS[state] || "");
    const step = el("div", { class: `step ${state}` }, [
      node,
      el("div", { class: "connector" }),
      el("div", { class: "label" }, s.label),
    ]);
    stepper.appendChild(step);
  });

  const caption = document.getElementById("pipeline-caption");
  if (contract.status === "processing") {
    const talk = AGENT_TALK[contract.current_stage] || "Working…";
    caption.innerHTML = `<span class="agent-name">●</span> ${talk}`;
  } else if (contract.status === "failed") {
    caption.textContent = "";
  } else {
    caption.textContent = "";
  }
}

function renderVerdictArea(contract) {
  const area = document.getElementById("verdict-area");
  area.innerHTML = "";
  if (contract.status === "completed") {
    const flags = (contract.risk_flags && contract.risk_flags.flags) || [];
    const critical = flags.some((f) => f.severity === "critical");
    const banner = el("div", { class: "verdict-banner neu-flat" }, [
      el("span", { class: "icon" }, critical ? "⚠️" : "✅"),
      el("div", {}, [
        el("div", { class: "title" }, "Verdict ready"),
        el(
          "div",
          { class: "sub" },
          critical
            ? `${flags.length} risk flag(s) found — review before approving the draft below.`
            : flags.length
            ? `${flags.length} minor flag(s) found — see below.`
            : "No playbook violations found."
        ),
      ]),
    ]);
    area.appendChild(banner);
  } else if (contract.status === "failed") {
    area.appendChild(
      el("div", { class: "error-banner" }, [
        el("strong", {}, "Pipeline failed partway through. "),
        "Nothing already completed was lost — see the fields and audit log below for what finished before the error. ",
        el("div", { style: "margin-top:8px; font-family: ui-monospace, monospace; font-size: 11.5px; opacity: 0.85;" }, contract.error || "Unknown error"),
      ])
    );
  }
}

// ---------------- Polling ----------------

const activePolls = new Map();

function pollContract(contractId) {
  if (activePolls.has(contractId)) return;

  document.getElementById("pipeline-block").style.display = "block";

  const tick = async () => {
    let contract;
    try {
      contract = await api(`/contracts/${contractId}`);
    } catch {
      return;
    }
    renderStepper(contract);
    renderVerdictArea(contract);
    renderDetail(contract);

    if (contract.status === "processing") {
      const t = setTimeout(tick, 1200);
      activePolls.set(contractId, t);
    } else {
      activePolls.delete(contractId);
      const auditLog = await api(`/contracts/${contractId}/audit-log`).catch(() => []);
      renderAuditLog(auditLog);
      loadClients(); // client/contract may be new or renamed
    }
  };
  tick();
}

// ---------------- Detail rendering ----------------

function severityBadge(sev) {
  return el("span", { class: `badge ${sev}` }, sev);
}

function field(label, value) {
  return el("div", { class: "field" }, [el("div", { class: "k" }, label), el("div", { class: "v" }, value)]);
}

function renderDetail(c) {
  const detail = document.getElementById("detail");
  detail.innerHTML = "";

  if (c.status === "processing" && !c.contract_type) {
    return; // nothing to show yet — the stepper covers it
  }

  const overview = el("div", { class: "panel neu-raised" });
  overview.appendChild(el("h2", {}, "📋 Overview"));
  const grid = el("div", { class: "grid-2" });
  grid.appendChild(field("Contract type", c.contract_type || "—"));
  grid.appendChild(field("Parties", (c.parties || []).join(" ↔ ") || "—"));
  grid.appendChild(field("Effective date", c.effective_date || "—"));
  grid.appendChild(field("Term length", c.term_length_months ? `${c.term_length_months} months` : "—"));
  overview.appendChild(grid);
  if (c.is_renewal_of) overview.appendChild(field("Renewal of contract", c.is_renewal_of));
  overview.appendChild(field("Prepared by", c.created_by || "—"));
  detail.appendChild(overview);

  if (c.deadline || c.status === "completed") {
    const deadlinePanel = el("div", { class: "panel neu-raised" });
    deadlinePanel.appendChild(el("h2", {}, "⏰ Renewal deadline"));
    if (c.deadline && c.deadline.cancel_by_date) {
      deadlinePanel.appendChild(field("Cancel by", c.deadline.cancel_by_date));
      deadlinePanel.appendChild(field("Reminders", (c.deadline.reminder_dates || []).join(", ") || "—"));
      deadlinePanel.appendChild(field("Reasoning", c.deadline.reasoning || "—"));
      deadlinePanel.appendChild(
        el("a", { class: "link", href: `/contracts/${c.id}/calendar.ics` }, "Download .ics (not added to any calendar automatically)")
      );
    } else {
      deadlinePanel.appendChild(el("div", { class: "empty-state" }, "No auto-renewal deadline (no auto-renewal clause detected, or dates were missing)."));
    }
    detail.appendChild(deadlinePanel);
  }

  if (c.diff) {
    const diffPanel = el("div", { class: "panel neu-raised" });
    diffPanel.appendChild(el("h2", {}, "🔀 What changed since prior version"));
    const changes = c.diff.changes || [];
    if (changes.length === 0) {
      diffPanel.appendChild(el("div", { class: "empty-state" }, "No substantive differences detected."));
    } else {
      for (const change of changes) {
        const entry = el("div", { class: "diff-entry" });
        entry.appendChild(el("div", { class: "clause-type" }, [change.clause_type + " ", severityBadge(change.materiality)]));
        entry.appendChild(el("div", { class: "row old" }, [el("span", { class: "tag" }, "before"), change.old_value]));
        entry.appendChild(el("div", { class: "row new" }, [el("span", { class: "tag" }, "after"), change.new_value]));
        diffPanel.appendChild(entry);
      }
    }
    if (c.diff.summary) diffPanel.appendChild(el("div", { class: "draft-note" }, c.diff.summary));
    detail.appendChild(diffPanel);
  }

  if (c.risk_flags) {
    const riskPanel = el("div", { class: "panel neu-raised" });
    riskPanel.appendChild(el("h2", {}, "🛡️ Flagged risks"));
    const flags = c.risk_flags.flags || [];
    if (flags.length === 0) {
      riskPanel.appendChild(el("div", {}, [severityBadge("ok"), " Nothing outside the playbook."]));
    } else {
      for (const f of flags) {
        const flagEl = el("div", { class: "risk-flag" });
        flagEl.appendChild(el("div", { class: "clause-type" }, [f.clause_type + " ", severityBadge(f.severity)]));
        flagEl.appendChild(el("div", { class: "issue" }, f.issue));
        riskPanel.appendChild(flagEl);
      }
    }
    if (c.risk_flags.summary) riskPanel.appendChild(el("div", { class: "draft-note" }, c.risk_flags.summary));
    detail.appendChild(riskPanel);
  }

  if (c.draft_email) {
    const emailPanel = el("div", { class: "panel neu-raised" });
    emailPanel.appendChild(el("h2", {}, "✉️ Draft summary email"));
    emailPanel.appendChild(el("div", { class: "draft-badge" }, [el("span", { class: "dot" }), "Draft — awaiting human approval"]));
    emailPanel.appendChild(el("div", { class: "email-subject" }, c.draft_email.subject));
    emailPanel.appendChild(el("div", { class: "email-body neu-inset" }, c.draft_email.body));
    emailPanel.appendChild(el("div", { class: "draft-note" }, "This has not been sent to anyone. A human reviews and sends it manually."));
    detail.appendChild(emailPanel);
  }

  const auditPanel = el("div", { class: "panel neu-raised" });
  auditPanel.id = "audit-panel";
  auditPanel.appendChild(el("h2", {}, "🧾 Audit log — who/what knew this, and when"));
  auditPanel.appendChild(el("div", { class: "empty-state", id: "audit-loading" }, "Loading…"));
  detail.appendChild(auditPanel);

  if (c.status !== "processing") {
    api(`/contracts/${c.id}/audit-log`)
      .then(renderAuditLog)
      .catch(() => {});
  }
}

function renderAuditLog(rows) {
  const panel = document.getElementById("audit-panel");
  if (!panel) return;
  panel.querySelectorAll("table, .empty-state").forEach((e) => e.remove());
  if (!rows || rows.length === 0) {
    panel.appendChild(el("div", { class: "empty-state" }, "No audit entries yet."));
    return;
  }
  const table = el("table", { class: "data-table" });
  table.appendChild(
    el("tr", {}, [
      el("th", {}, "Agent"),
      el("th", {}, "Timestamp"),
      el("th", {}, "By"),
      el("th", {}, "Confidence"),
      el("th", {}, "Tokens (in / out)"),
      el("th", {}, "Input hash"),
    ])
  );
  for (const row of rows) {
    table.appendChild(
      el("tr", {}, [
        el("td", {}, row.agent_name),
        el("td", {}, new Date(row.created_at).toLocaleString()),
        el("td", {}, row.performed_by || "—"),
        el("td", {}, row.confidence != null ? row.confidence.toFixed(2) : "—"),
        el("td", { class: "tokens" }, row.input_tokens != null ? `${row.input_tokens} / ${row.output_tokens}` : "—"),
        el("td", { class: "hash" }, row.input_hash.slice(0, 14) + "…"),
      ])
    );
  }
  panel.appendChild(table);
}

// ---------------- Upload ----------------

const fileInput = document.getElementById("file");
fileInput.addEventListener("change", () => {
  const label = document.getElementById("file-drop-text");
  const wrap = document.getElementById("file-drop-label");
  if (fileInput.files.length) {
    label.textContent = fileInput.files[0].name;
    wrap.classList.add("has-file");
  } else {
    label.textContent = "Choose a PDF file…";
    wrap.classList.remove("has-file");
  }
});

document.getElementById("upload-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const provider = document.getElementById("provider").value;
  const model = document.getElementById("model").value;
  const status = document.getElementById("upload-status");
  const btn = document.getElementById("upload-btn");

  if (!fileInput.files.length) return;

  const formData = new FormData();
  formData.append("file", fileInput.files[0]);
  const params = new URLSearchParams();
  if (provider) params.set("provider", provider);
  if (model) params.set("model", model);

  btn.disabled = true;
  status.className = "upload-status";
  status.textContent = "Uploading…";
  document.getElementById("detail").innerHTML = "";
  document.getElementById("verdict-area").innerHTML = "";

  try {
    const res = await fetch(`/contracts/upload?${params.toString()}`, {
      method: "POST",
      body: formData,
      credentials: "same-origin",
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    const result = await res.json();
    status.textContent = "Submitted — running in the background. You can navigate away; progress is saved server-side.";
    pollContract(result.contract_id);
  } catch (err) {
    status.className = "upload-status error";
    status.textContent = `Failed: ${err.message}`;
  } finally {
    btn.disabled = false;
  }
});

// ---------------- History view ----------------

async function loadHistory() {
  const container = document.getElementById("history-table");
  container.innerHTML = '<div class="empty-state">Loading…</div>';
  const rows = await api("/history").catch(() => []);
  container.innerHTML = "";
  if (rows.length === 0) {
    container.appendChild(el("div", { class: "empty-state" }, "No activity yet."));
    return;
  }
  const table = el("table", { class: "data-table" });
  table.appendChild(
    el("tr", {}, [
      el("th", {}, "Client"),
      el("th", {}, "Contract"),
      el("th", {}, "Agent"),
      el("th", {}, "Performed by"),
      el("th", {}, "Tokens"),
      el("th", {}, "Timestamp"),
    ])
  );
  for (const row of rows) {
    const tr = el("tr", {}, [
      el("td", {}, row.client_name || "—"),
      el("td", {}, row.contract_type || "—"),
      el("td", {}, row.agent_name),
      el("td", {}, row.performed_by || "—"),
      el("td", { class: "tokens" }, row.input_tokens != null ? `${row.input_tokens} / ${row.output_tokens}` : "—"),
      el("td", {}, new Date(row.created_at).toLocaleString()),
    ]);
    if (row.contract_id) {
      tr.style.cursor = "pointer";
      tr.onclick = () => {
        document.querySelector('#topnav button[data-view="workspace"]').click();
        pollContract(row.contract_id);
      };
    }
    table.appendChild(tr);
  }
  container.appendChild(table);
}

// ---------------- Usage view ----------------

async function loadUsage() {
  const stats = document.getElementById("usage-stats");
  const byAgent = document.getElementById("usage-by-agent");
  stats.innerHTML = '<div class="empty-state">Loading…</div>';
  byAgent.innerHTML = "";

  const summary = await api("/usage/summary").catch(() => null);
  stats.innerHTML = "";
  if (!summary) {
    stats.appendChild(el("div", { class: "empty-state" }, "No usage data yet."));
    return;
  }

  const row = el("div", { class: "stat-row" });
  row.appendChild(statTile(summary.total_calls, "LLM calls"));
  row.appendChild(statTile(summary.total_input_tokens.toLocaleString(), "Input tokens"));
  row.appendChild(statTile(summary.total_output_tokens.toLocaleString(), "Output tokens"));
  stats.appendChild(row);

  if (summary.by_agent.length) {
    const table = el("table", { class: "data-table" });
    table.appendChild(
      el("tr", {}, [
        el("th", {}, "Agent"),
        el("th", {}, "Calls"),
        el("th", {}, "Input tokens"),
        el("th", {}, "Output tokens"),
      ])
    );
    for (const a of summary.by_agent) {
      table.appendChild(
        el("tr", {}, [
          el("td", {}, a.agent_name),
          el("td", {}, String(a.calls)),
          el("td", { class: "tokens" }, a.input_tokens.toLocaleString()),
          el("td", { class: "tokens" }, a.output_tokens.toLocaleString()),
        ])
      );
    }
    byAgent.appendChild(table);
  }
}

function statTile(num, label) {
  return el("div", { class: "stat-tile neu-flat" }, [
    el("div", { class: "num" }, String(num)),
    el("div", { class: "lbl" }, label),
  ]);
}

// ---------------- Boot ----------------

checkAuth();
