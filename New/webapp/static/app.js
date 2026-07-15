"use strict";

const $ = (id) => document.getElementById(id);

const EXAMPLE_SEQUENCES = [
  ["e1", "e2", "e3"],
  ["e1", "e3", "e2"],
  ["e1", "e2", "e3", "e4"],
  ["e2", "e3"],
];

// --------------------------------------------------------------------------- //
// API
// --------------------------------------------------------------------------- //

async function postJSON(url, body) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return res.json();
}

// --------------------------------------------------------------------------- //
// Job runner — supports several concurrent jobs (root run + refine panels).
// ui: { progress(s), done(result), fail(msg), stopped() }
// --------------------------------------------------------------------------- //

function createJob(ui) {
  const job = {
    id: null,
    timer: null,
    suppressModal: false,     // true after the user responds, until state leaves "awaiting"
    suppressedWarning: null,
    active: false,
  };

  job.start = async (body) => {
    const res = await postJSON("/api/start", body);
    if (res.error) {
      ui.fail(res.error);
      return false;
    }
    job.id = res.job;
    job.active = true;
    job.suppressModal = false;
    job.suppressedWarning = null;
    poll();
    return true;
  };

  job.stop = async () => {
    if (!job.active) return;
    await postJSON("/api/control", { job: job.id, action: "stop" });
  };

  job.cancelPolling = () => {
    clearTimeout(job.timer);
    job.active = false;
  };

  // Continuous poll loop: runs until a terminal state. Never stops on "awaiting".
  function poll() {
    clearTimeout(job.timer);
    job.timer = setTimeout(async () => {
      if (!job.active) return;
      try {
        const s = await fetch("/api/status?job=" + job.id).then((r) => r.json());
        handleStatus(s);
      } catch (e) {
        job.active = false;
        ui.fail("Lost connection to server: " + e.message);
      }
    }, 250);
  }

  function handleStatus(s) {
    if (s.error && !s.state) {
      job.active = false;
      ui.fail(s.error);
      return;
    }
    ui.progress(s);

    if (s.state === "awaiting") {
      const warning = s.warning || "Runtime warning raised, but no message was provided.";
      if (!job.suppressModal || warning !== job.suppressedWarning) {
        showModal(warning, job);
      }
      poll(); // keep polling so we notice when the worker resumes
      return;
    }

    // Left the awaiting state: clear modal + the suppression latch.
    job.suppressModal = false;
    job.suppressedWarning = null;
    if (modalJob === job) hideModal();

    if (s.state === "done") {
      job.active = false;
      ui.done(s.result);
    } else if (s.state === "stopped") {
      job.active = false;
      ui.stopped();
    } else if (s.state === "error") {
      job.active = false;
      ui.fail("Halted: " + (s.error || s.message));
    } else {
      poll(); // still running
    }
  }

  return job;
}

// --------------------------------------------------------------------------- //
// Modal (runtime warning) — shared; routes the decision to the awaiting job.
// --------------------------------------------------------------------------- //

let modalJob = null;
let modalBusy = false;

function showModal(msg, job) {
  modalJob = job;
  modalBusy = false;
  $("modal-msg").textContent = msg;
  $("modal-continue").disabled = false;
  $("modal-abort").disabled = false;
  $("modal").classList.remove("hidden");
}
function hideModal() {
  $("modal").classList.add("hidden");
  modalJob = null;
}
async function modalDecision(cont) {
  const job = modalJob;
  if (!job || modalBusy) return;
  modalBusy = true;
  job.suppressedWarning = $("modal-msg").textContent;
  $("modal-continue").disabled = true;
  $("modal-abort").disabled = true;
  hideModal();
  job.suppressModal = true; // don't re-show this warning while the worker resumes
  try {
    const res = await postJSON("/api/control", {
      job: job.id,
      action: cont ? "continue" : "abort",
    });
    if (res.error) {
      throw new Error(res.error);
    }
  } catch (e) {
    job.suppressModal = false;
    showModal("Could not send warning response to server: " + e.message, job);
  } finally {
    modalBusy = false;
  }
  // The poll loop is already running; it will pick up the new state.
}

// --------------------------------------------------------------------------- //
// Root run (sidebar)
// --------------------------------------------------------------------------- //

const rootJob = createJob({
  progress(s) {
    const pct = Math.round((s.frac || 0) * 100);
    $("progress-fill").style.width = pct + "%";
    $("progress-pct").textContent = pct + "%";
    $("progress-stage").textContent = s.stage || "running";
    $("progress-msg").textContent = `[${s.stage}] ${s.message || ""}`;
  },
  done(result) {
    renderResult(result, {
      summary: $("summary"),
      results: $("results"),
      title: "Initial run",
      rowLabels: null,
      clusterPrefix: "C",
    });
    setStatus("Done.", "ok");
    rootFinish();
  },
  fail(msg) {
    setStatus(msg, "error");
    rootFinish();
  },
  stopped() {
    setStatus("Stopped by user.", "error");
    rootFinish();
  },
});

function rootFinish() {
  $("run").disabled = false;
  $("stop").disabled = true;
}

async function startRun() {
  const events = $("events").value.trim();
  const body = {
    input_text: $("sequences").value,
    input_format: $("input-format").value,
    sequence_column: $("sequence-column").value.trim() || "sequence",
    r: parseInt($("r").value, 10),
    t: parseInt($("t").value, 10),
    events: events ? events.split(",").map((s) => s.trim()).filter(Boolean) : null,
    detect_bidirectional: $("bidir").checked,
  };

  $("results").innerHTML = "";
  $("summary").className = "summary-empty muted";
  $("summary").textContent = "Running...";
  closeAllRefinePanels(); // refinements of the previous run no longer apply
  setStatus("", "");

  const ok = await rootJob.start(body);
  if (!ok) return;
  $("run").disabled = true;
  $("stop").disabled = false;
  $("progress-wrap").classList.remove("hidden");
}

// --------------------------------------------------------------------------- //
// Rendering
// --------------------------------------------------------------------------- //

function setStatus(msg, cls) {
  const el = $("status");
  el.textContent = msg;
  el.className = "status" + (cls ? " " + cls : "");
}

function loadExample() {
  $("sequences").value = JSON.stringify(EXAMPLE_SEQUENCES, null, 2);
  $("input-format").value = "json";
  $("sequence-column").value = "sequence";
  $("r").value = "2";
  $("t").value = "60";
  if (!$("events").value.trim()) {
    $("events").value = "e1,e2,e3";
  }
  setStatus("Loaded example input.", "ok");
}

function formatJSON() {
  try {
    const parsed = JSON.parse($("sequences").value);
    $("sequences").value = JSON.stringify(parsed, null, 2);
    $("input-format").value = "json";
    setStatus("Formatted input JSON.", "ok");
  } catch (e) {
    setStatus("Format JSON only works for JSON input: " + e.message, "error");
  }
}

async function loadInputFile(event) {
  const file = event.target.files && event.target.files[0];
  if (!file) return;
  const text = await file.text();
  $("sequences").value = text;
  const lower = file.name.toLowerCase();
  if (lower.endsWith(".csv")) {
    $("input-format").value = "csv";
  } else if (lower.endsWith(".json")) {
    $("input-format").value = "json";
  } else {
    $("input-format").value = "auto";
  }
  setStatus(`Loaded ${file.name}.`, "ok");
}

// Stable distinct color per cluster (hue rotation over the source index).
// Lightness comes from the theme (--cluster-l): dark tones on light bg,
// light tones on dark bg — recolors automatically on theme toggle.
function clusterColor(i, total) {
  const hue = Math.round((360 / Math.max(total, 1)) * i + 210) % 360;
  return `hsl(${hue} 58% var(--cluster-l, 40%))`;
}

function seqLabel(seq) {
  return seq.length ? seq.join(" → ") : "(empty after filter)";
}

// ctx: {
//   summary: element for the metric grid,
//   results: element for the result cards,
//   title:   breadcrumb label for this run (used by refine panels),
//   rowLabels: null for the root run, or an array mapping the submitted-input
//              row index -> original display row number (refine panels).
// }
function renderResult(result, ctx) {
  // Old server process (started before the membership feature) won't send
  // these fields; warn instead of rendering a misleading empty membership.
  const staleServer = !("source_members" in result);
  const sequences = result.sequences || [];
  // Pre-filter sequences used as refine input so each refine level always
  // starts from the raw data, not an already-filtered copy.
  const originalSequences = result.original_sequences || sequences;
  const members = result.source_members || [];
  // Original input positions of the valid rows (emptied rows are excluded
  // from n, so display numbering must come from here, not the array index).
  const seqIdx = result.sequence_indices || [];
  const inputIdx = (i) => (seqIdx[i] !== undefined ? seqIdx[i] : i);
  const rowNum = (i) =>
    ctx.rowLabels ? ctx.rowLabels[inputIdx(i)] : inputIdx(i) + 1;

  // Each DAG of each source subset is one cluster, with a global id.
  // clusters[k] = { source index, dag index within source, member row indices }
  const clusters = [];
  result.sources.forEach((subset, si) => {
    subset.forEach((dag, di) => {
      clusters.push({
        k: clusters.length,
        source: si,
        dagIdx: di,
        dag,
        members: (members[si] || [])[di] || [],
      });
    });
  });
  const total = clusters.length;

  // Rows covered by at least one cluster, for the summary metric.
  const assigned = new Set();
  clusters.forEach((c) => c.members.forEach((i) => assigned.add(i)));

  const clusterPrefix = ctx.clusterPrefix || "C";

  ctx.summary.className = "summary-grid";
  ctx.summary.innerHTML = [
    ["Loaded Rows", result.n_loaded !== undefined ? result.n_loaded : "—"],
    ["Valid Rows n", result.n],
    ["Emptied By Filter", result.n_empty !== undefined ? result.n_empty : "—"],
    ["Distinct DAGs |S|", result.num_S],
    ["Qualifying Subsets |C|", result.num_C],
    ["Sources", result.sources.length],
    ["Clusters (DAGs)", total],
    ["Clustered Rows", staleServer ? "—" : `${assigned.size}/${result.n}`],
  ].map(([label, value]) => (
    `<div class="metric"><div class="metric-label">${label}</div><div class="metric-value">${value}</div></div>`
  )).join("");

  const wrap = ctx.results;
  wrap.innerHTML = "";
  if (staleServer) {
    const note = document.createElement("div");
    note.className = "status error";
    note.textContent =
      "Server is running an older version without cluster membership — " +
      "restart it (python webapp/server.py) and run again.";
    wrap.appendChild(note);
  }
  if (!total) {
    wrap.innerHTML += '<div class="muted">No source subsets.</div>';
    return;
  }

  if (!staleServer) {
    const toolbar = document.createElement("div");
    toolbar.className = "result-toolbar";

    const mkBtn = (label, handler) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "ghost";
      btn.textContent = label;
      btn.addEventListener("click", handler);
      toolbar.appendChild(btn);
    };
    mkBtn("Export Cluster Summary", () =>
      exportClusterSummaryCSV(result, clusters, rowNum, clusterPrefix)
    );
    mkBtn("Export Row Assignments", () =>
      exportRowAssignmentsCSV(result, clusters, rowNum, sequences, clusterPrefix)
    );
    wrap.appendChild(toolbar);
  }

  const refine = (k) => {
    const c = clusters[k];
    const rows = c.members.map((i) => ({
      num: rowNum(i),
      seq: originalSequences[inputIdx(i)] || [],
    }));
    openRefinePanel({
      label: `${clusterPrefix}${k + 1}`,
      color: clusterColor(k, total),
      rows,
      parentTitle: ctx.title,
      dag: c.dag,
    });
  };

  // Heat map first (needs membership data).
  if (!staleServer) {
    wrap.appendChild(renderHeatmapCard(result, clusters, total, refine, clusterPrefix));
  }

  let clusterId = 0;
  result.sources.forEach((subset, si) => {
    const card = document.createElement("div");
    card.className = "source-card";

    const h = document.createElement("h4");
    h.textContent =
      `Source #${si + 1} — ${subset.length} cluster${subset.length > 1 ? "s" : ""} (one per DAG)`;
    card.appendChild(h);

    const meta = document.createElement("div");
    meta.className = "source-meta";
    meta.textContent =
      "Minimal incoming-closure witness set under the current rules. " +
      "Each DAG below is a cluster; a row belongs to it iff that DAG is in the row's S_i.";
    card.appendChild(meta);

    const row = document.createElement("div");
    row.className = "dag-row";
    subset.forEach((dag) => {
      const k = clusterId++;
      const color = clusterColor(k, total);
      const idxs = clusters[k].members;
      const pctVal = result.n ? Math.round((idxs.length / result.n) * 100) : 0;
      const pct = idxs.length && pctVal === 0 ? "<1" : pctVal;

      const box = document.createElement("div");
      box.className = "dag-box cluster-box";
      box.style.borderColor = color;

      const head = document.createElement("div");
      head.className = "cluster-box-head";
      const dot = document.createElement("span");
      dot.className = "cluster-dot";
      dot.style.background = color;
      head.appendChild(dot);
      head.appendChild(document.createTextNode(
        staleServer ? `${clusterPrefix}${k + 1}`
                    : `${clusterPrefix}${k + 1} — ${idxs.length}/${result.n} rows (${pct}%)`));
      if (!staleServer && idxs.length) {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "ghost refine-btn";
        btn.textContent = "Refine ▸";
        btn.title = "Re-cluster only this cluster's rows with new r / t / event filters";
        btn.addEventListener("click", () => refine(k));
        head.appendChild(btn);
      }
      box.appendChild(head);

      box.appendChild(renderDag(dag));
      const cap = document.createElement("div");
      cap.className = "dag-caption";
      cap.textContent = dag.edges.map((e) => `${e[0]}→${e[1]}`).join("  ");
      box.appendChild(cap);

      if (!staleServer) {
        const chips = document.createElement("div");
        chips.className = "member-chips";
        if (!idxs.length) {
          chips.innerHTML = '<span class="muted">No rows covered.</span>';
        } else {
          idxs.forEach((idx) => {
            const chip = document.createElement("span");
            chip.className = "member-chip";
            chip.style.borderColor = color;
            chip.innerHTML = `<b>#${rowNum(idx)}</b> ${seqLabel(sequences[idx] || [])}`;
            chips.appendChild(chip);
          });
        }
        box.appendChild(chips);
      }
      row.appendChild(box);
    });
    card.appendChild(row);
    wrap.appendChild(card);
  });

  if (!staleServer) {
    wrap.appendChild(renderAssignmentTable(sequences, clusters, total, rowNum, clusterPrefix));
  }
}

// Row -> cluster assignment table. A row can match several cluster DAGs
// (within or across sources) or none.
function renderAssignmentTable(sequences, clusters, total, rowNum, clusterPrefix) {
  const card = document.createElement("div");
  card.className = "source-card";
  const h = document.createElement("h4");
  h.textContent = "Row → Cluster Assignment";
  card.appendChild(h);
  const meta = document.createElement("div");
  meta.className = "source-meta";
  meta.textContent =
    "Each valid sequence and the cluster DAG(s) covering it. Rows may belong to several clusters, or none.";
  card.appendChild(meta);

  const rowClusters = sequences.map(() => []);
  clusters.forEach((c, k) => c.members.forEach((i) => rowClusters[i].push(k)));

  const table = document.createElement("table");
  table.className = "assign-table";
  table.innerHTML = "<thead><tr><th>Row</th><th>Sequence</th><th>Clusters</th></tr></thead>";
  const tbody = document.createElement("tbody");
  sequences.forEach((seq, i) => {
    const tr = document.createElement("tr");
    const tdRow = document.createElement("td");
    tdRow.textContent = `#${rowNum(i)}`;
    const tdSeq = document.createElement("td");
    tdSeq.className = "assign-seq";
    tdSeq.textContent = seqLabel(seq);
    const tdCl = document.createElement("td");
    if (!rowClusters[i].length) {
      const badge = document.createElement("span");
      badge.className = "cluster-badge unclustered";
      badge.textContent = "unclustered";
      tdCl.appendChild(badge);
      tr.className = "row-unclustered";
    } else {
      rowClusters[i].forEach((c) => {
        const color = clusterColor(c, total);
        const badge = document.createElement("span");
        badge.className = "cluster-badge";
        badge.style.borderColor = color;
        badge.style.color = color;
        badge.textContent = `${clusterPrefix || "C"}${c + 1}`;
        tdCl.appendChild(badge);
      });
    }
    tr.appendChild(tdRow);
    tr.appendChild(tdSeq);
    tr.appendChild(tdCl);
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);
  card.appendChild(table);
  return card;
}

// --------------------------------------------------------------------------- //
// CSV export — two files
// --------------------------------------------------------------------------- //

function downloadCSV(csv, filename) {
  const blob = new Blob([csv], { type: "text/csv" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
}

const esc = (v) => `"${String(v).replace(/"/g, '""')}"`;
const row = (...cols) => cols.map(esc).join(",");

// cluster_summary.csv — one row per cluster.
// Columns: cluster_id, source, n_rows, pct_of_total, dag_edges, member_row_numbers
function exportClusterSummaryCSV(result, clusters, rowNum, clusterPrefix) {
  const lines = [row(
    "cluster_id", "source", "n_rows", "pct_of_total",
    "dag_edges", "member_row_numbers"
  )];
  clusters.forEach((c) => {
    const id  = `${clusterPrefix}${c.k + 1}`;
    const pct = result.n ? (c.members.length / result.n * 100).toFixed(1) : "0";
    const edges = c.dag.edges.map(([u, v]) => `${u}→${v}`).join("  ");
    const memberNums = c.members.map((i) => rowNum(i)).join("|");
    lines.push(row(id, `Source ${c.source + 1}`, c.members.length, pct + "%", edges, memberNums));
  });
  downloadCSV(lines.join("\n"), "cluster_summary.csv");
}

// row_assignments.csv — one row per input sequence.
// Columns: row, sequence, n_clusters, cluster_ids, cluster_sources, is_clustered
function exportRowAssignmentsCSV(result, clusters, rowNum, sequences, clusterPrefix) {
  const rowClusters = sequences.map(() => []);
  clusters.forEach((c) => c.members.forEach((i) => rowClusters[i].push(c)));

  const lines = [row(
    "row", "sequence", "n_clusters",
    "cluster_ids", "cluster_sources", "is_clustered"
  )];
  sequences.forEach((seq, i) => {
    const cs      = rowClusters[i];
    const ids     = cs.map((c) => `${clusterPrefix}${c.k + 1}`).join("|");
    const sources = cs.map((c) => `Source ${c.source + 1}`).join("|");
    lines.push(row(
      rowNum(i), seqLabel(seq), cs.length,
      ids, sources, cs.length > 0 ? "true" : "false"
    ));
  });
  downloadCSV(lines.join("\n"), "row_assignments.csv");
}

// --------------------------------------------------------------------------- //
// Heat map (S&P 500 / finviz style treemap)
//   sector  = source subset
//   tile    = cluster (DAG); area ∝ rows covered; green intensity = coverage %
// --------------------------------------------------------------------------- //

// Squarified treemap (Bruls et al.). items: [{value, ...}]; returns
// [{it, x, y, w, h}] filling the given rect. With keepOrder the input order
// is preserved (so Source 1 stays top-left and cluster ids read in sequence)
// at the cost of slightly worse aspect ratios than the size-sorted classic.
function squarify(items, x, y, w, h, keepOrder) {
  const out = [];
  const totalVal = items.reduce((s, it) => s + it.value, 0);
  if (!totalVal || w <= 4 || h <= 4) return out;
  const scale = (w * h) / totalVal;
  let queue = items
    .map((it) => ({ it, area: it.value * scale }))
    .filter((r) => r.area > 0);
  if (!keepOrder) queue.sort((a, b) => b.area - a.area);

  const worst = (row, len) => {
    const s = row.reduce((q, r) => q + r.area, 0);
    let m = 0;
    row.forEach((r) => {
      m = Math.max(m, (len * len * r.area) / (s * s), (s * s) / (len * len * r.area));
    });
    return m;
  };

  let rx = x, ry = y, rw = w, rh = h;
  while (queue.length) {
    const len = Math.min(rw, rh);
    const row = [queue[0]];
    let i = 1;
    while (i < queue.length && worst(row.concat(queue[i]), len) <= worst(row, len)) {
      row.push(queue[i]);
      i++;
    }
    queue = queue.slice(row.length);
    const s = row.reduce((q, r) => q + r.area, 0);
    const thick = s / len;
    let off = 0;
    row.forEach((r) => {
      const breadth = r.area / thick;
      if (rw >= rh) {
        out.push({ it: r.it, x: rx, y: ry + off, w: thick, h: breadth });
      } else {
        out.push({ it: r.it, x: rx + off, y: ry, w: breadth, h: thick });
      }
      off += breadth;
    });
    if (rw >= rh) { rx += thick; rw -= thick; }
    else { ry += thick; rh -= thick; }
  }
  return out;
}

// Stock-market ramp: red (worst) → amber (mid) → dark green (best).
// Piecewise so the transition through amber is visible and the ends are saturated.
function heatColor(t) {
  let hue, sat, l;
  if (t < 0.5) {
    const u = t * 2;                      // 0..1 within red-amber leg
    hue = Math.round(u * 40);             // 0 (red) → 40 (amber)
    sat = 78;
    l   = Math.round(32 + u * 6);        // 32% → 38%
  } else {
    const u = (t - 0.5) * 2;             // 0..1 within amber-green leg
    hue = Math.round(40 + u * 88);       // 40 (amber) → 128 (dark green)
    sat = Math.round(74 + u * 6);        // 74% → 80%
    l   = Math.round(38 - u * 14);       // 38% → 24% (darker = richer green)
  }
  return `hsl(${hue} ${sat}% ${l}%)`;
}


function renderHeatmapCard(result, clusters, total, onRefine, clusterPrefix) {
  const card = document.createElement("div");
  card.className = "source-card";
  const h = document.createElement("h4");
  h.textContent = "Cluster Heat Map";
  card.appendChild(h);
  const meta = document.createElement("div");
  meta.className = "source-meta";
  meta.textContent =
    "Stock-market style treemap: each block is a source subset, each tile a cluster. " +
    "Tile area ∝ rows covered; brighter green = higher coverage. Click a tile to refine.";
  card.appendChild(meta);

  const box = document.createElement("div");
  box.className = "heatmap";
  card.appendChild(box);

  const draw = () => drawHeatmap(box, result, clusters, total, onRefine, clusterPrefix);
  // Width is only known once the card is in the DOM.
  requestAnimationFrame(draw);
  registerHeatmapRedraw(box, draw);
  return card;
}

function drawHeatmap(box, result, clusters, total, onRefine, clusterPrefix) {
  box.innerHTML = "";
  const W = box.clientWidth || 640;
  // Height grows with the number of clusters (sqrt keeps it sublinear), so
  // runs with many sources get room instead of cramming into a fixed strip.
  const H = Math.max(240, Math.min(900, Math.round(Math.sqrt(clusters.length) * 120 + 40)));
  box.style.height = H + "px";

  const SECTOR_HEAD = 18, PAD = 2;
  const allCounts = clusters.map((c) => c.members.length);
  const maxMembers = Math.max(1, ...allCounts);
  // Floor at 12% of largest cluster so small tiles stay visible and clickable.
  // Equal-sized clusters still get equal area (both exceed the floor).
  const tileValue = (c) => Math.max(c.members.length, maxMembers * 0.12, 0.5);

  const sectors = result.sources.map((subset, si) => {
    const cls = clusters.filter((c) => c.source === si);
    return { si, cls, value: cls.reduce((s, c) => s + tileValue(c), 0) };
  });

  squarify(sectors, 0, 0, W, H, true).forEach((sr) => {
    const sec = document.createElement("div");
    sec.className = "hm-sector";
    sec.style.left = sr.x + PAD + "px";
    sec.style.top = sr.y + PAD + "px";
    sec.style.width = Math.max(sr.w - PAD * 2, 0) + "px";
    sec.style.height = Math.max(sr.h - PAD * 2, 0) + "px";
    box.appendChild(sec);

    const innerW = Math.max(sr.w - PAD * 2, 0);
    const innerH = Math.max(sr.h - PAD * 2 - SECTOR_HEAD, 0);
    // Sectors are laid out by size (treemap), not source order, so the label
    // is the only way to find a source — keep one as long as anything fits,
    // shortening to "S7" on narrow sectors. Tooltip covers the tiny rest.
    const showHead = innerH > 24 && innerW > 34;
    sec.title = `Source ${sr.it.si + 1}`;

    if (showHead) {
      const head = document.createElement("div");
      head.className = "hm-sector-label";
      head.textContent = innerW > 90 ? `Source ${sr.it.si + 1}` : `S${sr.it.si + 1}`;
      sec.appendChild(head);
    }

    // Color: proportional to (members / source_max).
    // Best in source = 1.0 (dark green). Others scale down from there.
    // A cluster at 90% of the max looks nearly as green; one at 1% looks red.
    // No forced-red for "smallest in source" — only genuinely tiny clusters
    // (small relative to the source's best) go red.
    const secMax = Math.max(1, ...sr.it.cls.map((c) => c.members.length));
    const heatT = (c) => Math.pow(c.members.length / secMax, 0.6);

    const tileItems = sr.it.cls.map((c) => ({ value: tileValue(c), c }));
    const top = showHead ? SECTOR_HEAD : 0;
    const areaH = showHead ? innerH : Math.max(sr.h - PAD * 2, 0);
    squarify(tileItems, 0, top, innerW, areaH, true).forEach((tr) => {
      const c = tr.it.c;
      const pctVal = result.n ? Math.round((c.members.length / result.n) * 100) : 0;
      const pct = c.members.length && pctVal === 0 ? "<1" : pctVal;
      const tile = document.createElement("div");
      tile.className = "hm-tile";
      tile.style.left = tr.x + 1 + "px";
      tile.style.top = tr.y + 1 + "px";
      tile.style.width = Math.max(tr.w - 2, 0) + "px";
      tile.style.height = Math.max(tr.h - 2, 0) + "px";
      tile.style.background = heatColor(heatT(c));
      tile.title =
        `Source ${c.source + 1} · Cluster ${c.k + 1} — ${c.members.length}/${result.n} rows (${pct}%)\n` +
        c.dag.edges.map((e) => `${e[0]}→${e[1]}`).join("  ") +
        (c.members.length ? "\nClick to refine this cluster." : "");
      if (c.members.length) {
        tile.classList.add("hm-clickable");
        tile.addEventListener("click", () => onRefine(c.k));
      }
      // Drop label lines before they clip: full info needs real room, the
      // medium size keeps name + percent, slivers show the name only.
      const full = tr.w >= 96 && tr.h >= 74;
      const medium = tr.w >= 56 && tr.h >= 46;
      tile.innerHTML =
        `<span class="hm-tile-name">${clusterPrefix || "C"}${c.k + 1}</span>` +
        (full ? `<span class="hm-tile-sub">${c.members.length} rows</span>` : "") +
        (full || medium ? `<span class="hm-tile-pct">${pct}%</span>` : "");
      sec.appendChild(tile);
    });
  });
}

// Redraw heat maps whenever the box itself changes size (covers both window
// resize and the root panel shrinking when a refine panel opens/closes).
function registerHeatmapRedraw(box, draw) {
  let roTimer = null;
  const ro = new ResizeObserver(() => {
    clearTimeout(roTimer);
    roTimer = setTimeout(draw, 120);
  });
  ro.observe(box);
  // Clean up observer when the box leaves the DOM.
  new MutationObserver((_, mo) => {
    if (!box.isConnected) { ro.disconnect(); mo.disconnect(); }
  }).observe(document.body, { childList: true, subtree: true });
}


// --------------------------------------------------------------------------- //
// Refine panels — iterative clustering of one cluster's rows with new
// r / t / event filters, shown as extra columns next to the initial results.
// --------------------------------------------------------------------------- //

let refineCounter = 0;

function closeAllRefinePanels() {
  document.querySelectorAll(".refine-panel").forEach((p) => {
    if (p._job) p._job.cancelPolling();
    p.remove();
  });
}

// info: { label, color, rows: [{num, seq}], parentTitle, dag }
function openRefinePanel(info) {
  const uid = ++refineCounter;
  const title = `${info.parentTitle} ▸ ${info.label}`;
  const panel = document.createElement("div");
  panel.className = "panel refine-panel";

  const distinctEvents = [...new Set(info.rows.flatMap((r) => r.seq))];

  panel.innerHTML = `
    <div class="refine-head">
      <span class="cluster-dot" style="background:${info.color}"></span>
      <div class="refine-titles">
        <div class="refine-title">Refine ${info.label}</div>
        <div class="refine-crumb">${title} — ${info.rows.length} rows</div>
      </div>
      <button type="button" class="icon-btn refine-close" title="Close panel">✕</button>
    </div>
    <div class="refine-form">
      <div class="row">
        <label>r — max subset size
          <input id="rf-r-${uid}" type="number" min="1" value="${$("r").value || 2}" />
        </label>
        <label>t — coverage %
          <input id="rf-t-${uid}" type="number" min="0" max="100" value="${$("t").value || 100}" />
        </label>
      </div>
      <label>Events filter (optional, comma-separated)
        <input id="rf-events-${uid}" type="text" placeholder="${distinctEvents.slice(0, 6).join(",")}" />
      </label>
      <div class="controls">
        <button id="rf-run-${uid}" class="primary" type="button">Run on ${info.rows.length} rows</button>
        <button id="rf-stop-${uid}" class="danger" type="button" disabled>Stop</button>
      </div>
      <div id="rf-progress-${uid}" class="muted refine-progress"></div>
      <div id="rf-status-${uid}" class="status"></div>
    </div>
    <div id="rf-summary-${uid}" class="summary-empty muted">Set parameters and run to re-cluster these rows.</div>
    <div id="rf-results-${uid}"></div>
  `;

  panel.querySelector(".refine-close").addEventListener("click", () => {
    if (panel._job) panel._job.cancelPolling();
    if (panel._job && panel._job.active) panel._job.stop();
    panel.remove();
  });

  const setPanelStatus = (msg, cls) => {
    const el = $(`rf-status-${uid}`);
    el.textContent = msg;
    el.className = "status" + (cls ? " " + cls : "");
  };
  const finishPanel = () => {
    $(`rf-run-${uid}`).disabled = false;
    $(`rf-stop-${uid}`).disabled = true;
  };

  const job = createJob({
    progress(s) {
      const pct = Math.round((s.frac || 0) * 100);
      $(`rf-progress-${uid}`).textContent = `[${s.stage}] ${pct}% ${s.message || ""}`;
    },
    done(result) {
      renderResult(result, {
        summary: $(`rf-summary-${uid}`),
        results: $(`rf-results-${uid}`),
        title,
        // Submitted-input index -> original display row number.
        rowLabels: info.rows.map((r) => r.num),
        clusterPrefix: info.label + ".",
      });
      setPanelStatus("Done.", "ok");
      finishPanel();
    },
    fail(msg) {
      setPanelStatus(msg, "error");
      finishPanel();
    },
    stopped() {
      setPanelStatus("Stopped by user.", "error");
      finishPanel();
    },
  });
  panel._job = job;

  $("panels").appendChild(panel);
  panel.scrollIntoView({ behavior: "smooth", inline: "end", block: "nearest" });

  $(`rf-run-${uid}`).addEventListener("click", async () => {
    const events = $(`rf-events-${uid}`).value.trim();
    const body = {
      sequences: info.rows.map((r) => r.seq),
      r: parseInt($(`rf-r-${uid}`).value, 10),
      t: parseInt($(`rf-t-${uid}`).value, 10),
      events: events ? events.split(",").map((s) => s.trim()).filter(Boolean) : null,
      detect_bidirectional: $("bidir").checked,
    };
    $(`rf-results-${uid}`).innerHTML = "";
    const summary = $(`rf-summary-${uid}`);
    summary.className = "summary-empty muted";
    summary.textContent = "Running...";
    setPanelStatus("", "");
    const ok = await job.start(body);
    if (!ok) return;
    $(`rf-run-${uid}`).disabled = true;
    $(`rf-stop-${uid}`).disabled = false;
  });
  $(`rf-stop-${uid}`).addEventListener("click", () => job.stop());
}

// --------------------------------------------------------------------------- //
// DAG rendering — left-to-right layered SVG with curved (cubic-bezier) edges.
// --------------------------------------------------------------------------- //

function renderDag(dag) {
  const SVG_NS = "http://www.w3.org/2000/svg";
  const nodes = dag.vertices.slice();
  const edges = dag.edges;

  // Longest-path layering => x coordinate (left to right).
  const succ = {}, indeg = {};
  nodes.forEach((n) => { succ[n] = []; indeg[n] = 0; });
  edges.forEach(([u, v]) => { succ[u].push(v); indeg[v]++; });

  // Topological order (edges go forward by construction).
  const layer = {};
  nodes.forEach((n) => (layer[n] = 0));
  // Relax along a topo order obtained via Kahn's algorithm.
  const q = nodes.filter((n) => indeg[n] === 0);
  const indegCopy = Object.assign({}, indeg);
  const topo = [];
  while (q.length) {
    const u = q.shift();
    topo.push(u);
    succ[u].forEach((v) => {
      layer[v] = Math.max(layer[v], layer[u] + 1);
      if (--indegCopy[v] === 0) q.push(v);
    });
  }

  // Group nodes by layer for vertical stacking.
  const byLayer = {};
  let maxLayer = 0;
  nodes.forEach((n) => {
    (byLayer[layer[n]] = byLayer[layer[n]] || []).push(n);
    maxLayer = Math.max(maxLayer, layer[n]);
  });

  const COL = 90, ROW = 46, R = 16, padX = 24, padY = 24;
  let maxRows = 1;
  Object.values(byLayer).forEach((arr) => (maxRows = Math.max(maxRows, arr.length)));

  const width = padX * 2 + maxLayer * COL + R * 2;
  const height = padY * 2 + (maxRows - 1) * ROW + R * 2;

  const pos = {};
  Object.keys(byLayer).forEach((L) => {
    const arr = byLayer[L].sort();
    arr.forEach((n, i) => {
      pos[n] = {
        x: padX + R + Number(L) * COL,
        y: padY + R + i * ROW + (maxRows - arr.length) * ROW / 2,
      };
    });
  });

  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("width", width);
  svg.setAttribute("height", height);

  // arrowhead marker
  const defs = document.createElementNS(SVG_NS, "defs");
  defs.innerHTML =
    '<marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" ' +
    'markerHeight="7" orient="auto-start-reverse">' +
    '<path d="M0,0 L10,5 L0,10 z" class="dag-arrow"/></marker>';
  svg.appendChild(defs);

  // edges (curved)
  edges.forEach(([u, v]) => {
    const a = pos[u], b = pos[v];
    const path = document.createElementNS(SVG_NS, "path");
    const sx = a.x + R, sy = a.y;
    const tx = b.x - R, ty = b.y;
    const span = layer[v] - layer[u];
    let d;

    if (span > 1) {
      const blockers = nodes
        .filter((n) => layer[n] > layer[u] && layer[n] < layer[v])
        .filter((n) => {
          const p = pos[n];
          const lineY = sy + (ty - sy) * ((p.x - sx) / (tx - sx));
          return Math.abs(p.y - lineY) < R + 10;
        })
        .map((n) => pos[n].y);
      const mx = (sx + tx) / 2;
      if (blockers.length) {
        // Nudge only enough to miss the node, choosing the natural open side.
        const midY = (sy + ty) / 2;
        const blockerAvg = blockers.reduce((sum, y) => sum + y, 0) / blockers.length;
        const detourY = blockerAvg >= midY
          ? Math.max(12, Math.min(sy, ty, ...blockers) - R - 10)
          : Math.min(height - 12, Math.max(sy, ty, ...blockers) + R + 10);
        d = `M ${sx} ${sy} C ${mx} ${detourY}, ${mx} ${detourY}, ${tx} ${ty}`;
      } else {
        d = `M ${sx} ${sy} C ${mx} ${sy}, ${mx} ${ty}, ${tx} ${ty}`;
      }
    } else {
      const mx = (a.x + b.x) / 2;
      d = `M ${sx} ${sy} C ${mx} ${sy}, ${mx} ${ty}, ${tx} ${ty}`;
    }
    path.setAttribute("d", d);
    path.setAttribute("fill", "none");
    path.setAttribute("class", "dag-edge");
    path.setAttribute("stroke-width", "1.3");
    path.setAttribute("marker-end", "url(#ah)");
    path.setAttribute("opacity", "0.9");
    svg.appendChild(path);
  });

  // nodes
  nodes.forEach((n) => {
    const p = pos[n];
    const c = document.createElementNS(SVG_NS, "circle");
    c.setAttribute("cx", p.x);
    c.setAttribute("cy", p.y);
    c.setAttribute("r", R);
    c.setAttribute("class", "dag-node");
    c.setAttribute("stroke-width", "1.2");
    svg.appendChild(c);
    const txt = document.createElementNS(SVG_NS, "text");
    txt.setAttribute("x", p.x);
    txt.setAttribute("y", p.y + 4);
    txt.setAttribute("text-anchor", "middle");
    txt.textContent = n;
    svg.appendChild(txt);
  });

  return svg;
}

// --------------------------------------------------------------------------- //
// Theme
// --------------------------------------------------------------------------- //

function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  localStorage.setItem("theme", theme);
  $("theme-toggle").textContent = theme === "dark" ? "☀" : "☾";
  $("theme-toggle").title = theme === "dark" ? "Switch to light mode" : "Switch to dark mode";
}

applyTheme(
  localStorage.getItem("theme") ||
  (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light")
);

$("theme-toggle").addEventListener("click", () => {
  applyTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark");
});

// --------------------------------------------------------------------------- //
// Wire up
// --------------------------------------------------------------------------- //

$("run").addEventListener("click", startRun);
$("stop").addEventListener("click", () => rootJob.stop());
$("modal-continue").addEventListener("click", () => modalDecision(true));
$("modal-abort").addEventListener("click", () => modalDecision(false));
$("load-example").addEventListener("click", loadExample);
$("format-json").addEventListener("click", formatJSON);
$("input-file").addEventListener("change", loadInputFile);

document.addEventListener("click", (event) => {
  const actionButton = event.target.closest("[data-warning-action]");
  if (!actionButton) return;
  event.preventDefault();
  modalDecision(actionButton.dataset.warningAction === "continue");
}, true);
