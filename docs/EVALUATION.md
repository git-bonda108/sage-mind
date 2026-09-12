# Evaluation

## What exists today

**There is no automated test suite in this repository.** No test files, no CI configuration, no assertions, and no recorded metrics exist. Any quality claims about the generated reports are unverified.

### Edge handling visibly present in the code

These are the defensive measures that exist in `sage-mind.py`, enumerated from the source:

- **Bounded conversations:** every chat has a `max_turns` cap (1 for each reviewer, 2 for the critic–writer exchange), so no agent loop can run unbounded.
- **Termination sentinel:** agents append `TERMINATE`; `user_proxy_auto` and the Critic detect it via `is_termination_msg` lambdas, and the UI strips it from the rendered report.
- **Taxonomy fallback:** the sidebar uses `industry_to_domain.get(selected_industry, "N/A")`, so an unmapped industry degrades to `"N/A"` rather than raising.
- **Feedback guard:** the optional-feedback pass runs only when `feedback_text.strip()` is non-empty.

### What is absent

No retry logic, no timeouts, no exception handling around API calls, no validation of the model's markdown output, and no guard against submitting an empty topic. A network failure or API error surfaces as a raw Streamlit exception.

## Proposed evaluation harness

None of the following exists; it is a design for what this system should have.

### Golden dataset

A `tests/golden_topics.jsonl` of 20–30 entries shaped as:

```json
{"topic": "Machine Learning", "industry": "Information Technology",
 "learning_mode": "Binge Reading",
 "must_cover": ["supervised", "unsupervised", "reinforcement"],
 "must_not_cover": ["generative AI"]}
```

The `must_not_cover` field directly tests the researcher's core instruction ("do not include unrelated content such as generative AI unless explicitly requested").

### Gates (deterministic, run in CI)

1. **Structure gate:** the report contains all six required sections (Introduction, Key Concepts, Real-World Applications, Challenges, Future Trends, Conclusion) and the follow-up invitation sentence — automating what the CompletionReviewer currently checks by prompt.
2. **Sentinel gate:** no `TERMINATE` string survives into rendered output.
3. **URL gate:** every markdown link resolves with an HTTP 2xx/3xx within a timeout; broken citations fail the run (the system prompt demands "working, clickable" URLs, so this is testable).
4. **Quiz shape gate:** generated quizzes contain exactly N questions, 4 options each, one marked answer.

### Metrics (scored, tracked over time)

- **Topic fidelity:** LLM-judge score (1–5) for on-topic focus against `must_cover` / `must_not_cover`, averaged over the golden set; regression threshold on the average.
- **Latency and cost:** wall-clock and token usage per pipeline run, per stage — the sequential reviewer panel makes this worth tracking before/after any parallelization.

### Unit layer

The agent pipeline can be smoke-tested without paid API calls by faking the OpenAI endpoint (e.g. pointing `base_url` at a stub) and asserting that `initiate_chats` is invoked with the expected three-stage sequence and carryover strings. `EnsembleContentAgent.process` should get a unit test first — it currently indexes the completion response as a dict, which does not match the `openai>=1.0` client's return type (see ARCHITECTURE.md, Observed limitations).
