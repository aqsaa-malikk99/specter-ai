# Contract Renewal & Risk Radar — Project Spec

**Purpose of this doc:** a build-ready spec for an agentic pipeline that ingests a contract, files it under the right client, extracts renewal/risk-critical clauses, diffs it against prior versions, and surfaces deadlines and risks to a human — nothing auto-sent, nothing auto-scheduled without sign-off.

**Why this project:** most contract losses trace back to missed dates (auto-renewal windows) or one-sided clauses (indemnification, uncapped liability) that nobody flagged in time — not to nobody reading the document. This system targets that specific failure mode with a multi-agent pipeline, rather than trying to compete with full clause-review platforms like Kira or Legora.

---

## 1. System Overview

```
                    ┌──────────────────┐
   PDF / scan  ───► │  Orchestrator     │
   / email          │  (routes contract │
                     │  through agents)  │
                     └─────────┬─────────┘
                               │
        ┌──────────────────────┼──────────────────────┐
        ▼                      ▼                       ▼
┌───────────────┐   ┌────────────────────┐   ┌──────────────────┐
│ 1. Intake &    │   │ 2. Clause          │   │ 3. Diff Agent     │
│ Classification │──►│ Extraction Agent   │──►│ (only if a prior  │
│ Agent          │   │                    │   │ version exists)   │
└───────────────┘   └────────────────────┘   └─────────┬─────────┘
                                                          ▼
                     ┌────────────────────┐   ┌──────────────────┐
                     │ 5. Deadline Agent   │◄──│ 4. Risk &        │
                     │ (.ics + reminders)  │   │ Ambiguity Agent  │
                     └─────────┬───────────┘   └────────┬─────────┘
                               ▼                          ▼
                     ┌──────────────────────────────────────┐
                     │  6. Notify / Report Agent              │
                     │  (drafts summary email — human sends)  │
                     └──────────────────────────────────────┘
```

**Design principle: agents are specialists, the orchestrator is dumb on purpose.** Each agent does one job and returns structured JSON. The orchestrator just routes and branches (e.g. skip step 3 if there's no prior contract on file). This is the same shape as a real LLM-gateway setup — a routing layer over specialised tool-calling agents — which is worth naming explicitly in the interview.

---

## 2. Agent Specs

### 2.1 Intake & Classification Agent
**Input:** raw file (PDF/scan/forwarded email text)
**Does:**
- OCR if scanned (or direct text extraction if native PDF)
- Extracts: contracting parties, contract type, effective date, governing law, term length
- Matches to an existing client/company profile (fuzzy match on party name) or creates a new one
- Files the contract under that profile

**Output:**
```json
{
  "client_profile_id": "string",
  "contract_type": "string",
  "parties": ["string"],
  "effective_date": "ISO date",
  "term_length_months": "number|null",
  "is_renewal_of": "contract_id|null"
}
```

### 2.2 Clause Extraction Agent
**Input:** contract text + classification output
**Does:** pulls out the risk-relevant clauses as structured data, each with a section/page reference and a confidence score (0–1). Low-confidence extractions get flagged for human review rather than silently asserted.

**Clauses to extract (v1):**
- Auto-renewal term + exact notice-window language
- Indemnification clause (mutual vs one-sided)
- Liability cap (present / absent / amount)
- Termination rights & triggers
- Confidentiality term length

**Output:** array of `{clause_type, text_excerpt, section_ref, confidence, structured_value}`

### 2.3 Diff Agent
**Runs only if** `is_renewal_of` is set.
**Does:** semantic diff between the two contracts' extracted clauses (not raw text diff — clause-level, so a reworded-but-equivalent clause doesn't false-flag).
**Output:** plain-English changelog: `{clause_type, old_value, new_value, materiality: "cosmetic"|"substantive"}`

### 2.4 Risk & Ambiguity Agent
**Input:** extracted clauses + a small firm-provided "playbook" (a JSON/YAML list of acceptable fallback positions — e.g. "liability cap must be ≥ 12 months' fees")
**Does:** flags clauses that fall outside the playbook, plus anything the extraction agent scored below a confidence threshold.
**Output:** array of `{clause_type, issue, severity: "info"|"warn"|"critical"}`

### 2.5 Deadline Agent
**Input:** auto-renewal clause structured value
**Does:** computes the actual "must-cancel-by" date from the notice window language (e.g. "90 days before renewal" → real date), generates reminder points (90/30/7 days out), and produces a downloadable `.ics` file.
**Output:** `.ics` file + `{cancel_by_date, reminder_dates[]}`

### 2.6 Notify / Report Agent
**Input:** outputs of steps 2–5
**Does:** compiles everything into a single draft email — changelog, flagged risks, upcoming deadline — for a human to review and send. **Never auto-sends.**

---

## 3. Human-in-the-loop boundary (important, and worth saying out loud in the interview)

Nothing in this system auto-emails a client, auto-books a court date, or auto-writes to a live calendar without a person approving it first. In a regulated environment, a silently-acting agent is a liability, not a feature. Every agent output is a *draft* or a *flag* — a human always signs off before anything leaves the system or touches a calendar. This is a design constraint, not a missing feature — and it's the kind of judgment call that shows you understand where agentic autonomy is appropriate and where it isn't.

---

## 4. Audit Log

Every agent call — timestamp, input hash, output, confidence — gets logged. This isn't just nice-to-have logging; in a legal context it answers "who/what knew this and when," which matters for SRA-style accountability. Simple approach: append-only JSON lines file or SQLite table, one row per agent invocation.

---

## 5. Suggested Tech Stack

| Layer | Choice | Why |
|---|---|---|
| Orchestration | Simple Python state machine, or LangGraph if you want to demonstrate graph-based agent routing | LangGraph is a stronger interview talking point since it maps directly onto the diagram above |
| LLM calls | Claude (Sonnet) via Anthropic API, tool-use for structured JSON extraction | Consistent with your existing Prova project, keeps the stack coherent |
| OCR | `pytesseract` or a vision-capable Claude call on the rasterized PDF page | Vision-call approach handles messy scans better than plain OCR |
| Storage | SQLite for client profiles + contract history (Postgres if you want it deployable) | Simple, no infra overhead for a portfolio project |
| Diffing | Clause-level, not raw text — compare structured `clause_type` → `structured_value` pairs | Raw text diff produces noisy, useless output on legal documents |
| Calendar output | `ics` Python library | Zero dependency on any calendar provider for v1 |
| Frontend | Minimal — upload box, client profile list, contract detail view with flagged clauses highlighted | Doesn't need to be polished; the pipeline is the point |

---

## 6. Phased Build Plan

**Phase 1 — Core pipeline, one contract at a time**
- Intake & Classification Agent (skip company matching at first — just extract fields)
- Clause Extraction Agent (auto-renewal + notice window only, to start)
- Deadline Agent (.ics output)
- No diff, no risk playbook yet — get one contract flowing end-to-end first

**Phase 2 — Add the comparison layer**
- Client/company profile matching and filing
- Diff Agent (needs at least two versions of a contract to test against — use a real SaaS contract and a lightly-edited renewal version)

**Phase 3 — Risk pass**
- Risk & Ambiguity Agent with a small hand-written playbook (3–5 rules is enough to demonstrate the concept)
- Notify/Report Agent compiling everything into a draft email

**Phase 4 — Polish for interview demo**
- Audit log visible in the UI
- A short "why human-in-the-loop" note baked into the demo itself, not just spoken — e.g. a visible "Draft — awaiting approval" state on the email/calendar output

---

## 7. What to say in the interview

- Frame it as: *"I built a small agentic pipeline around the single most common way contracts actually cost money — missed renewal windows and one-sided clauses — rather than trying to rebuild what Kira or Legora already do."*
- Name the orchestration pattern explicitly: routing layer + specialist agents, each with a narrow job and structured output.
- Lead with the human-in-the-loop design choice unprompted — it signals you're thinking about deployment in a regulated environment, not just "can I make an agent do a thing."
