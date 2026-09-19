export const ADVISORY_THRESHOLDS = Object.freeze({
  warningRows: 200,
  warningDistinctEvents: 11,
});

function selectedSequence(sequence, events) {
  if (!events?.length) return sequence;
  const selected = new Set(events);
  return sequence.filter((event) => selected.has(String(event)));
}

function inspectJsonSequences(inputText, inputFormat, events) {
  const trimmed = (inputText || "").trim();
  if (inputFormat === "csv" || (!trimmed.startsWith("[") && inputFormat === "auto")) {
    return { exact: false, rows: Math.max(0, trimmed.split(/\r?\n/).length - 1) };
  }
  try {
    const parsed = JSON.parse(trimmed);
    if (!Array.isArray(parsed)) return { exact: false, parseError: "Input must be a list of sequences." };
    if (!parsed.every(Array.isArray)) return { exact: false, parseError: "Every sequence must be a list." };
    const scoped = parsed.map((sequence) => selectedSequence(sequence, events));
    return {
      exact: true,
      rows: parsed.length,
      maxDistinctEvents: Math.max(0, ...scoped.map((sequence) => new Set(sequence.map(String)).size)),
    };
  } catch {
    return { exact: false, parseError: "JSON could not be parsed. The browser worker will validate it if you continue." };
  }
}

export function assessBrowserRequest(request) {
  const errors = [];
  const warnings = [];
  const r = Number(request.r);
  const t = Number(request.t);

  if (!Number.isInteger(r) || r < 1) {
    errors.push("r must be a positive integer.");
  }
  if (!Number.isInteger(t) || t < 0 || t > 100) {
    errors.push("t must be an integer from 0 to 100.");
  }

  if ("sequences" in request) {
    const sequences = request.sequences;
    if (!Array.isArray(sequences)) {
      errors.push("Sequences must be a list.");
    } else {
      assessSequenceShape(sequences, request.events, errors, warnings);
    }
    return { errors, warnings };
  }

  const inspected = inspectJsonSequences(
    request.input_text || "",
    request.input_format || "auto",
    request.events,
  );
  if (inspected.parseError) warnings.push(inspected.parseError);
  if (inspected.rows >= ADVISORY_THRESHOLDS.warningRows) {
    warnings.push(`${inspected.rows} rows may take noticeable time on this device.`);
  }
  if (inspected.maxDistinctEvents >= ADVISORY_THRESHOLDS.warningDistinctEvents) {
    warnings.push(`${inspected.maxDistinctEvents} distinct selected events in one sequence can make exact search expensive.`);
  }
  if (r >= 3) {
    warnings.push(`r = ${r} can substantially increase exact subset search time.`);
  }
  if (t < 80) {
    warnings.push(`Coverage below 80% can produce many qualifying subsets.`);
  }
  return { errors, warnings };
}

function assessSequenceShape(sequences, events, errors, warnings) {
  const maxDistinctEvents = Math.max(
    0,
    ...sequences
      .filter(Array.isArray)
      .map((sequence) => new Set(selectedSequence(sequence, events).map(String)).size),
  );
  if (maxDistinctEvents >= ADVISORY_THRESHOLDS.warningDistinctEvents) {
    warnings.push(`${maxDistinctEvents} distinct selected events in one sequence can make exact search expensive.`);
  }
  if (sequences.length >= ADVISORY_THRESHOLDS.warningRows) {
    warnings.push(`${sequences.length} rows may take noticeable time on this device.`);
  }
}
