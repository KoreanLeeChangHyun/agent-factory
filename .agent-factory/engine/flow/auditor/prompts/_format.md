---
doc_type: format_spec
version: "1.0"
description: >
  Shared output schema and few-shot example for all AT-01~AT-12 LLM judge prompts.
  Each AT-NN.md prompt includes this spec by reference in its output section.
---

# Auditor T3 — Shared Output Format

## Output Schema

Every AT-NN evaluation MUST return a single JSON object on one line.
No markdown fences, no preamble, no trailing text after the JSON.

```
{"at_id": "<AT-NN>", "score": <1-5>, "evidence": "<one-sentence rationale>", "verdict": "<PASS|WARN|FAIL>"}
```

### Field Definitions

| Field     | Type   | Constraints                                      |
|-----------|--------|--------------------------------------------------|
| `at_id`   | string | Exactly the item identifier, e.g. `"AT-01"`      |
| `score`   | int    | Integer 1–5 inclusive                            |
| `evidence`| string | One sentence (≤ 120 chars) citing a specific artifact element |
| `verdict` | string | Exactly `"PASS"`, `"WARN"`, or `"FAIL"` — derived from score |

### Score → Verdict Mapping

| Score | Verdict | Meaning                             |
|-------|---------|-------------------------------------|
| 5     | PASS    | Fully meets the criterion           |
| 4     | PASS    | Mostly meets the criterion          |
| 3     | WARN    | Partially meets; notable gaps       |
| 2     | FAIL    | Largely fails the criterion         |
| 1     | FAIL    | Does not meet the criterion at all  |

### Chain-of-Thought Instruction

Before producing the JSON output, reason step-by-step internally:
1. Identify the specific artifact element being evaluated.
2. Apply the PASS/WARN/FAIL criterion from the prompt.
3. Cite the exact phrase or absence of content that determines the score.
4. Produce the JSON as the final line of your response.

The JSON line MUST be the last line of output. Everything before it is
internal reasoning and will be discarded by the caller.

---

## Few-Shot Example — AT-01 PASS

**Input artifacts (abbreviated):**

```
<ticket_xml>
<goal>Implement AT-01~AT-12 LLM judge prompt templates for the Tier-2 Auditor
module, enabling advisory-only scoring of workflow run quality.</goal>
<target>13 markdown files under auditor/prompts/</target>
<criteria>All 12 AT files exist; gate_type meta correct; _format.md present</criteria>
</ticket_xml>
```

**Internal reasoning (not returned):**

The goal states a concrete achievement state in ≤ 2 sentences. It does not
mix constraints or implementation details. Length is well under 200 chars.
No MUST NOT or prohibition language appears inside the goal field.
Score: 5.

**Output (returned):**

```json
{"at_id": "AT-01", "score": 5, "evidence": "Goal states a single deliverable in one declarative sentence without mixing constraints.", "verdict": "PASS"}
```

---

## Few-Shot Example — AT-06 FAIL (Hard Gate)

**Input artifacts (abbreviated):**

```
<ticket_xml>
<goal>Run a stress test with 1000+ events intentionally to validate
the broker under load — MUST NOT exceed 500 events in production.</goal>
<context>Previous attempt ran only 100 events. The real purpose is an
infrastructure capacity check unrelated to broker logic.</context>
</ticket_xml>
```

**Internal reasoning (not returned):**

The goal says "stress test… intentionally" but the context reveals the true
purpose is "infrastructure capacity check". These are different objectives —
goal describes an execution method, not an achievement state; context describes
a different objective entirely. Mismatch detected.
Score: 1.

**Output (returned):**

```json
{"at_id": "AT-06", "score": 1, "evidence": "Goal describes execution method ('stress test intentionally') while context reveals different objective ('infrastructure capacity check').", "verdict": "FAIL"}
```
