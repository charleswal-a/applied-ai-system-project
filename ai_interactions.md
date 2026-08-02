# AI Interactions Log

> **Stretch features only.** Only fill in the sections that apply to stretch features you attempted. If you did not attempt a stretch feature, leave its section blank or delete it. This file is not required for the core project.

---

## Agentic Workflow (SF8)

> Document your experience using an AI agent (e.g., Cursor Agent, Claude, Copilot) to make multi-step changes autonomously.

**What task did you give the agent?**

I asked Claude Code to brainstorm additions to the existing recommender that would satisfy the assignment's requirement to add a RAG, Agentic workflow, Fine-Tuned/Specialized Model, or Reliability/Testing feature, fully integrated into the main app rather than a standalone script. I picked "Agentic workflow" from its options, and then had it design and implement the feature end-to-end.

**Prompts used:**

- "Brainstorm some possible additions to this existing music recommender project... To make your project more advanced, it must include at least one of the following AI features: RAG, Agentic workflow, Fine-Tuned or Specialized Model, Reliability or Testing System... The feature should be fully integrated into the main application logic..."
- Selected "Agentic workflow" from the options it presented.
- Approved its implementation plan (parse free-text request → check for catalog contradictions → score → have the model review/summarize or ask a clarifying question → loop) after it walked me through the design.

**What did the agent generate or change?**

- New `src/agent.py`: the four pipeline functions (`parse_profile_from_text`, `check_catalog_guardrails`, `review_and_summarize`, `refine_profile`) plus the JSON schemas used to constrain the model's structured output.
- Rewrote `src/main.py` to replace the hardcoded `user_prefs` dict with an interactive free-text prompt, the parse → guardrail → recommend → review/clarify loop (max 2 rounds), logging setup, and a manual-input fallback if the AI pipeline is unavailable.
- Small change to `src/recommender.py`'s `load_songs` to raise a clear `ValueError` (with row number) on malformed CSV rows instead of an opaque traceback.
- New `tests/test_agent.py` covering the deterministic guardrail-check logic (genre/mood not in catalog, energy out of range, acoustic/genre contradiction) — no network calls required.
- Added `anthropic` to `requirements.txt`, added `logs/` to `.gitignore`, and updated `README.md` with the API key setup step and a new "AI-Assisted Mode" section.

**What did you verify or fix manually?**

I ran `pytest` to confirm the existing recommender tests still pass unchanged alongside the new guardrail tests, and reviewed the guardrail thresholds (e.g. the 0.3 average-acousticness cutoff for flagging a genre/acoustic contradiction) against the actual catalog data in `data/songs.csv` to make sure they'd actually trigger on the k-pop/metal/contradictory profiles already documented in the Limitations section. I also confirmed the app fails with a clear message (not a stack trace) when `ANTHROPIC_API_KEY` is unset, and that it falls back to manual prompts if an API call errors out.

---

## Design Pattern (SF10)

> Document how AI helped you choose or implement a design pattern.

**Which design pattern did you use?**

<!-- e.g., Strategy, Factory, Observer, etc. -->

**How did AI help you brainstorm or implement it?**

<!-- Describe the conversation or suggestions that led to your decision -->

**How does the pattern appear in your final code?**

<!-- Point to the relevant class or method -->
