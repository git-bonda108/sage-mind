# Hardening

## Current posture

This is a local-first prototype. Grounded in what `sage-mind.py` actually does:

- **Authentication:** none. The Streamlit app has no login; anyone who can reach the port can run pipelines against the configured OpenAI key.
- **Secrets handling:** correct for a prototype — `OPENAI_API_KEY` is read from the environment via `python-dotenv`; no credential is committed to the repository (verified across the full git history). There is, however, no `.gitignore`, so an accidentally created `.env` would be one `git add .` away from being committed.
- **Code execution surface:** `user_proxy_auto` is configured with `code_execution_config={..., "use_docker": False}`. If any agent reply contains a code block, AutoGen will execute it on the host machine with no container isolation. With `human_input_mode="NEVER"`, no human approves that execution.
- **Output rendering:** model output is rendered with `st.markdown`; the custom-CSS block uses `unsafe_allow_html=True`. Model-generated content is displayed without sanitization.
- **Error handling:** none around API calls; failures surface as raw exceptions in the UI.
- **Observability:** none — no logging, no token/cost accounting, no tracing of the multi-agent pipeline.
- **Cost controls:** none. Each **Learn Now** click triggers at minimum eight model conversations (three pipeline stages plus five reviews), all on `gpt-4o`, with no rate limiting or per-user budget.

## Ladder to production

### Stage 1 — Identity and keys

- Add a `.gitignore` covering `.env`, `.venv/`, `__pycache__/`, and AutoGen's `coding/` work directory.
- Move the API key from `.env` to a secrets manager appropriate to the deployment target (or `st.secrets` for Streamlit deployments); rotate the key on any suspicion of exposure.
- Disable code execution unless it is actually needed: set `code_execution_config=False` on the user proxy — nothing in the current pipeline requires executing model-emitted code. If it becomes needed, require `use_docker=True`.
- Put authentication in front of the app (reverse proxy with SSO/OIDC, or Streamlit's native auth where available) before exposing it beyond localhost.

### Stage 2 — Monitoring

- Wrap `initiate_chats` calls with try/except and show a friendly retry path instead of stack traces.
- Add structured logging per pipeline stage (topic hash, stage, latency, token usage from the completion objects) so cost per run is measurable — the prerequisite for any model-tiering decision.
- Track failure modes explicitly: API errors, empty-topic submissions, `TERMINATE` leakage.

### Stage 3 — Deployment

- Containerize with a pinned Python version; replace the current `requirements.txt` (which mixes pinned and unpinned entries, duplicates `langchain` and `python-dotenv`, and includes many unused libraries) with a minimal, fully pinned dependency set for reproducible builds.
- Run Streamlit behind a reverse proxy with TLS; set an explicit `server.address`/`server.port` and disable usage-stats telemetry as policy dictates.
- Add per-session rate limiting and an OpenAI spend cap, since a single unauthenticated user can trigger unbounded `gpt-4o` usage.

### Stage 4 — Compliance and abuse resistance

- Treat model output as untrusted: the report and quiz render user-steered model text as markdown, and the researcher is instructed to include external URLs — link destinations are unvetted. Sanitize or vet rendered links before organizational use.
- Prompt-injection posture: the topic and feedback fields flow verbatim into agent prompts; with code execution disabled (Stage 1) the blast radius is content quality rather than host compromise, which is the right trade.
- Define data retention: currently nothing is stored, which is the simplest compliant posture; if run persistence is added (see ARCHITECTURE.md, Extending), decide retention and access rules at that point.

## Secrets removed from HEAD — rotate these credentials and purge history

None. No credentials, key files, or populated `.env` files were found at HEAD or anywhere in the repository's history.
