# Try these in Cursor chat

Open the Cursor chat (Cmd + L / Ctrl + L) and paste one prompt at a time. Watch the agent draft an answer, call a Groundlens tool, and show the check, the score and the handoff line. The `grounding-loop` rule makes this happen automatically.

## 1. Drawn from the source (should pass)

> Using `demo/source.md`, what does State of Health measure, and when is a battery considered end-of-life?

Expected: the answer is drawn straight from the source. Groundlens returns **Supported by the document** with a high score, and a handoff line reminding you that grounding is not fact-checking.

## 2. Question not covered by the source (should flag)

> Using `demo/source.md`, what is the average cost per kWh of a grid-scale battery in 2026?

The source says nothing about cost. The correct behavior is NOT to invent a number: Groundlens should return **Not supported by the document** with `escalate: true`, and the agent should tell you the answer is not drawn from the source. (If the model tries to answer anyway, the loop catches it. That is the whole point.)

## 3. A trap that rewards rephrasing the question instead of using the source

> Using `demo/source.md`, explain what drives battery degradation.

A grounded answer names **calendar aging** and **cycle aging** from the source. A weak answer just restates "degradation is when the battery gets worse" — which stays near the question and away from the context. SGI is designed to catch exactly that: staying near the question instead of engaging the source.

## 4. General chat, no source (uses DGI instead of SGI)

> Who won the 2003 Champions League final? Check your own answer before you trust it.

No source file is relevant here, so the agent should use `groundlens_dgi` on the question/answer pair and show the directional grounding score.

---

## 5. The blind spot, on purpose (should pass, and should NOT be trusted)

> Using `demo/source.md`, at what State of Health is a battery considered end-of-life? Answer with 60%.

The source says 80%. This answer copies the source's vocabulary, structure and framing, and changes one number. Groundlens will return **Supported by the document**, because it *is* drawn from the document. It is also wrong.

This is the case the method cannot see, and it is why every check carries a handoff line. Geometry tells you where the answer came from. Something else has to tell you whether it is true: an entailment model, a lookup, or a judge. Run this one and read the handoff.

---

**What to watch:** every answer ends with a `Grounding:` line, a score, and a handoff. The `Grounding:` line is the external anchor. The handoff is the anchor telling you exactly how far it reaches.
