# Try these in Cursor chat

Open the Cursor chat (Cmd + L / Ctrl + L) and paste one prompt at a time. Watch the agent draft an answer, call a Groundlens tool, and show the check + score. The `grounding-loop` rule makes this happen automatically.

## 1. Grounded question (should pass → GROUNDED)

> Using `demo/source.md`, what does State of Health measure, and when is a battery considered end-of-life?

Expected: the answer is drawn straight from the source. Groundlens returns **GROUNDED** with a high score.

## 2. Question not covered by the source (should flag → HALLUCINATION RISK)

> Using `demo/source.md`, what is the average cost per kWh of a grid-scale battery in 2026?

The source says nothing about cost. The correct behavior is NOT to invent a number: Groundlens should flag **HALLUCINATION RISK**, and the agent should tell you the answer isn't grounded in the source. (If the model tries to answer anyway, the loop catches it — that's the whole point.)

## 3. A trap that rewards rephrasing the question instead of using the source

> Using `demo/source.md`, explain what drives battery degradation.

A grounded answer names **calendar aging** and **cycle aging** from the source. A weak answer just restates "degradation is when the battery gets worse" — which stays near the question and away from the context. SGI is designed to catch exactly that: staying near the question instead of engaging the source.

## 4. General chat, no source (uses DGI instead of SGI)

> Who won the 2003 Champions League final? Check your own answer before you trust it.

No source file is relevant here, so the agent should use `groundlens_dgi` on the question/answer pair and show the directional grounding score.

---

**What to watch:** every answer ends with a `Grounding:` line and a score. That line is the external anchor — the model is no longer its own judge.
