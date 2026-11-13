const STYLE = "\n.farm-ui { padding:12px 4px; color:inherit; min-height:470px; }\n.farm-ui * { box-sizing:border-box; }\n.farm-ui h2 { font-size:1rem; margin:0 0 4px; }\n.farm-ui h3 { font-size:.94rem; margin:0 0 6px; }\n.farm-muted { color:var(--text-muted); font-size:.72rem; line-height:1.55; }\n.farm-grid { display:grid; grid-template-columns:minmax(230px,34%) minmax(0,1fr); gap:12px; margin-top:14px; }\n.farm-panel { background:var(--card-bg); border:1px solid var(--stroke); border-radius:9px; padding:14px; min-width:0; }\n.farm-ui button { border:1px solid var(--stroke); border-radius:6px; background:var(--card-bg); color:inherit; padding:7px 10px; font:inherit; font-size:.73rem; cursor:pointer; min-height:33px; }\n.farm-ui button:disabled { opacity:.5; cursor:default; }\n.farm-ui button:focus-visible, .farm-ui input:focus-visible { outline:2px solid var(--accent); outline-offset:2px; }\n.farm-toggle { display:grid; grid-template-columns:1fr 1fr; gap:4px; margin-bottom:12px; }\n.farm-toggle button.selected, .farm-targets button.selected { border-color:var(--accent); background:var(--selected); color:var(--accent); }\n.farm-ui input { width:100%; height:36px; padding:8px; border:1px solid var(--stroke); border-radius:6px; background:transparent; color:inherit; font:inherit; font-size:.76rem; }\n.farm-label { font-size:.72rem; font-weight:650; margin:0 0 6px; display:block; }\n.farm-targets { display:flex; flex-direction:column; max-height:440px; min-height:90px; overflow-y:auto; gap:4px; margin-top:10px; }\n.farm-targets button { text-align:left; border-color:transparent; background:transparent; }\n.farm-targets button:hover { background:var(--card-hover); }\n.farm-subtext { display:block; margin-top:3px; color:var(--text-muted); font-size:.65rem; }\n.farm-status { display:inline-block; border:1px solid var(--stroke); padding:5px 8px; border-radius:5px; margin:10px 0; font-size:.7rem; }\n.farm-divider { border-top:1px solid var(--stroke); margin:14px 0; }\n.farm-source-list { padding-left:20px; line-height:1.8; font-size:.74rem; }\n.farm-source-list a { color:var(--accent); }\n.farm-actions { display:flex; flex-wrap:wrap; gap:8px; margin-top:12px; }\n.farm-actions .primary { border-color:var(--accent); background:var(--accent); color:#102a35; }\n.farm-state { margin-top:12px; border:1px solid var(--stroke); border-radius:7px; padding:10px; }\n.farm-calibration-steps { max-height:185px; overflow-y:auto; padding-right:6px; }\n.farm-calibration-steps li { padding:4px 0; }\n.farm-calibration-steps li.farm-current-step { border-left:2px solid var(--accent); padding-left:8px; }\n@media(max-width:780px){.farm-grid{grid-template-columns:1fr}.farm-targets{max-height:180px}}\n";

function node(tag, className, value) {
  const item = document.createElement(tag);
  if (className) item.className = className;
  if (value !== undefined && value !== null) item.textContent = String(value);
  return item;
}

export function mount(container, context) {
  const state = {
    kind: "material", query: "", rows: [], selectedId: null,
    goal: "", detail: null, destroyed: false, request: 0, detailRequest: 0
  };
  const t = (key) => context.t(key);
  const style = node("style", "", STYLE);
  const root = node("main", "farm-ui");
  root.setAttribute("aria-label", t("Farming Assistant"));
  root.append(
    node("h2", "", t("Farming Assistant")),
    node("p", "farm-muted", t("Read-only preview. No game input or item spending."))
  );
  const grid = node("div", "farm-grid");
  const left = node("section", "farm-panel");
  const right = node("section", "farm-panel");
  const toggle = node("div", "farm-toggle");
  toggle.setAttribute("role", "group");
  toggle.setAttribute("aria-label", t("Target type"));
  const kinds = [["material", t("Materials")], ["mob", t("Mobs")]];
  const kindButtons = [];
  kinds.forEach(([kind, label]) => {
    const button = node("button", "", label);
    button.type = "button";
    button.addEventListener("click", () => {
      if (state.kind === kind) return;
      state.kind = kind;
      state.goal = "";
      state.selectedId = null;
      state.detail = null;
      updateKinds();
      void refresh();
    });
    kindButtons.push([kind, button]);
    toggle.append(button);
  });
  function updateKinds() {
    kindButtons.forEach(([kind, button]) => {
      const selected = state.kind === kind;
      button.classList.toggle("selected", selected);
      button.setAttribute("aria-pressed", String(selected));
    });
  }
  updateKinds();
  const label = node("label", "farm-label", t("Search by name"));
  label.htmlFor = "farm-search";
  const search = node("input");
  search.id = "farm-search";
  search.type = "search";
  search.maxLength = 120;
  search.placeholder = t("Find a material or mob");
  search.autocomplete = "off";
  const list = node("div", "farm-targets");
  list.setAttribute("role", "listbox");
  list.setAttribute("aria-label", t("Available targets"));
  left.append(toggle, label, search, list);
  grid.append(left, right);
  root.append(grid);
  container.replaceChildren(style, root);

  function renderList() {
    if (state.destroyed) return;
    list.replaceChildren();
    if (state.rows.length === 0) {
      list.append(node("p", "farm-muted", t("No matching targets.")));
      return;
    }
    state.rows.forEach((item) => {
      const selected = item.id === state.selectedId;
      const button = node("button", selected ? "selected" : "");
      button.type = "button";
      button.setAttribute("role", "option");
      button.setAttribute("aria-selected", String(selected));
      button.append(
        node("span", "", item.name),
        node("small", "farm-subtext", item.readiness.replaceAll("_", " ").toLowerCase())
      );
      button.addEventListener("click", () => {
        if (state.selectedId === item.id) return;
        state.selectedId = item.id;
        state.goal = "";
        state.detail = null;
        renderList();
        void refreshDetail();
      });
      list.append(button);
    });
  }

  function renderDetail() {
    if (state.destroyed) return;
    right.replaceChildren();
    const data = state.detail;
    if (!data) {
      right.append(node("p", "farm-muted", t("Select a target to inspect its readiness.")));
      return;
    }
    right.append(
      node("h3", "", data.target.name),
      node("p", "farm-muted", data.target.description),
      node("strong", "farm-status", data.readiness.replaceAll("_", " ")),
      node("p", "farm-muted", data.reason),
      node("div", "farm-divider"),
      node("label", "farm-label", t("Possible source mobs"))
    );
    const sources = data.source_candidates || [];
    if (sources.length) {
      const ul = node("ul", "farm-source-list");
      sources.forEach((source) => {
        const li = node("li");
        li.append(node("span", "", source.name + " · " + t("documented only")));
        try {
          const url = new URL(source.source_url);
          if (url.protocol === "https:" && !url.username && !url.password) {
            const link = node("a", "", t(" Reference"));
            link.href = url.href;
            link.target = "_blank";
            link.rel = "noopener noreferrer";
            li.append(link);
          }
        } catch {
          // An invalid external reference is not surfaced as a clickable link.
        }
        ul.append(li);
      });
      right.append(ul);
    } else {
      right.append(node("p", "farm-muted", t("No documented source mobs.")));
    }
    const audit = data.calibration || {};
    const candidateCount = Number(audit.receipt_candidate_count) || 0;
    const auditText = candidateCount
      ? t("Local receipt candidates (unverified): ") + String(candidateCount)
      : t("No qualified local receipt observations");
    right.append(node("p", "farm-muted", auditText));
    if ((Number(audit.rejected_manifest_count) || 0) > 0 ||
        audit.status === "AUDIT_INCOMPLETE") {
      right.append(node("p", "farm-muted",
        t("Evidence audit incomplete or invalid entries detected.")));
    }
    // Static local route metadata never makes Start executable.
    const routeAudit = data.route_calibration || {};
    const routeCount = Number(routeAudit.route_candidate_count) || 0;
    right.append(node("p", "farm-muted", routeCount
      ? t("Local route candidates (not live-qualified): ") + String(routeCount)
      : t("No qualified local route observations")));
    if ((Number(routeAudit.rejected_manifest_count) || 0) > 0 ||
        routeAudit.status === "ROUTE_AUDIT_INCOMPLETE") {
      right.append(node("p", "farm-muted",
        t("Route audit incomplete or invalid entries detected.")));
    }
    // Reconciliation is informational only; even matching numeric IDs do
    // not prove current game identity, drop receipts or route authorization.
    const comparison = data.reconciliation || {};
    const matches = Number(comparison.candidate_match_count) || 0;
    let comparisonText;
    if (matches) {
      comparisonText = t("Historical enemy-ID overlaps (not live-qualified): ") +
        String(matches);
    } else if (comparison.status === "AMBIGUOUS_RECEIPT_IDENTITIES") {
      comparisonText = t("Conflicting enemy IDs in local evidence; review required.");
    } else if (["INCOMPLETE_AUDITS", "TARGET_SCOPE_MISMATCH",
                "INVALID_AUDIT_SCHEMA", "UNRECOGNIZED_CATALOG_MOB",
                "SOURCE_NOT_MAPPED_TO_MATERIAL", "DUPLICATE_LOCAL_ROUTE_ID"]
                .includes(comparison.status)) {
      comparisonText = t("Receipt/route evidence requires review before matching.");
    } else {
      comparisonText = t("No matching local enemy IDs; route calibration required.");
    }
    right.append(node("p", "farm-muted", comparisonText));
    // This is an offline diagnostic, not a current-game authorization check.
    const preflight = data.preflight || {};
    right.append(node("p", "farm-muted",
      t("Calibration preflight: review required · game version: ") +
      String(preflight.game_version_check || "VERSION_NOT_OBSERVED")
        .replaceAll("_", " ").toLowerCase()));
    // Guidance is a read-only checklist. Historical references are never
    // presented as a completed live qualification or a Start permission.
    const guide = data.calibration_guide || {};
    if (guide.mode === "GUIDED_READ_ONLY" && Array.isArray(guide.steps)) {
      const section = node("section", "farm-state");
      section.setAttribute("aria-label", t("Guided calibration checklist"));
      section.append(node("h3", "", t("Guided calibration · read only")));
      section.append(node("p", "farm-muted", guide.notice || ""));
      const checklist = node("ol", "farm-source-list");
      checklist.classList.add("farm-calibration-steps");
      guide.steps.forEach((step) => {
        const item = node("li", "farm-muted");
        if (step.id === guide.next_step_id) item.classList.add("farm-current-step");
        item.append(
          node("strong", "", step.title),
          node("small", "farm-subtext",
            step.status === "HISTORICAL_REFERENCE_ONLY"
              ? t("Historical reference only · not live-verified")
              : t("Needs live verification")),
          node("div", "farm-subtext", step.instruction)
        );
        checklist.append(item);
      });
      section.append(checklist);
      right.append(section);
    }
    right.append(
      node("div", "farm-divider"),
      node("label", "farm-label", t("Target inventory total (optional)"))
    );
    const goal = node("input");
    goal.type = "number";
    goal.min = "1";
    goal.max = "9999999";
    goal.step = "1";
    goal.inputMode = "numeric";
    goal.placeholder = t("No target set");
    goal.value = state.goal;
    goal.addEventListener("change", () => {
      state.goal = goal.value;
      void refreshDetail();
    });
    right.append(goal, node("p", "farm-muted", t("Current inventory not measured.")));
    const actions = node("div", "farm-actions");
    [["Start", "primary"], ["Pause", ""], ["Stop", ""]].forEach(([title, cls]) => {
      const button = node("button", cls, t(title));
      button.type = "button";
      button.disabled = true;
      button.title = t("Current-game source and route qualification required");
      actions.append(button);
    });
    right.append(actions);
    const status = node("div", "farm-state");
    status.append(
      node("div", "farm-label", t("State") + ": " + data.run_state.replaceAll("_", " ")),
      node("div", "farm-muted", data.next_step)
    );
    right.append(status);
  }

  async function refreshDetail() {
    if (!state.selectedId || state.destroyed) {
      state.detail = null;
      renderDetail();
      return;
    }
    const seq = ++state.detailRequest;
    const id = state.selectedId;
    const kind = state.kind;
    try {
      const data = await context.query("preview", {
        kind, target_id: id, desired_total: state.goal
      });
      if (state.destroyed || seq !== state.detailRequest ||
          state.selectedId !== id || state.kind !== kind) return;
      state.detail = data;
      renderDetail();
    } catch (error) {
      if (state.destroyed || seq !== state.detailRequest) return;
      context.notify(error.message || String(error), "error");
      state.detail = null;
      renderDetail();
    }
  }

  async function refresh() {
    const seq = ++state.request;
    const kind = state.kind;
    try {
      const data = await context.query("targets", {kind, query: state.query});
      if (state.destroyed || seq !== state.request || kind !== state.kind) return;
      state.rows = data;
      if (!state.rows.some((item) => item.id === state.selectedId)) {
        state.selectedId = state.rows.length ? state.rows[0].id : null;
        state.goal = "";
        state.detail = null;
      }
      renderList();
      void refreshDetail();
    } catch (error) {
      if (state.destroyed || seq !== state.request) return;
      context.notify(error.message || String(error), "error");
      state.rows = [];
      state.selectedId = null;
      state.detail = null;
      renderList();
      renderDetail();
    }
  }

  search.addEventListener("input", () => {
    state.query = search.value;
    void refresh();
  });
  void refresh();
  return () => {
    state.destroyed = true;
    state.request++;
    state.detailRequest++;
  };
}
