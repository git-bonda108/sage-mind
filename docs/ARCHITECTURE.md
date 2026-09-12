# Architecture

Sage Mind is deliberately a single-module system: all agents, orchestration, and UI live in `sage-mind.py` (~385 lines). This document maps that file's real structure and the runtime behavior it produces.

## Component map

`sage-mind.py`, top to bottom:

| Section (lines, approx.) | Responsibility |
|---|---|
| Imports + `load_dotenv()` | Environment setup; `.env` supplies `OPENAI_API_KEY` |
| Custom CSS block | Streamlit theming via `st.markdown(..., unsafe_allow_html=True)` |
| `client = OpenAI()` + `call_openai_chat_completion` | Direct OpenAI client, used by `EnsembleContentAgent.process` |
| `industry_to_domain` dict | Static 19-industry taxonomy mapped to domain descriptions; drives the sidebar classification |
| Agent definitions | Ten AutoGen assistant agents sharing one `llm_config` (`gpt-4o`): DomainResearcher, EnsembleSynthesizer, Writer, QuizGenerator, Critic, and five reviewers (Legal, Consistency, TextAlignment, Completion, Meta) |
| `review_chats` + `register_nested_chats` | The Critic registers five single-turn nested review chats, triggered by the Writer |
| `user_proxy_auto` | `UserProxyAgent` with `human_input_mode="NEVER"`, TERMINATE-based termination, and code execution enabled (`work_dir="coding"`, `use_docker=False`) |
| Streamlit UI | Sidebar (classification, learning mode), topic form, quiz slider/button |
| Orchestration block | `autogen.initiate_chats` pipeline on form submit; separate `initiate_chats` calls for quiz generation and feedback |

## Data flow end to end

1. The user submits a topic; the app composes a `research_task` string embedding today's date, the topic, the selected industry, its domain description, and the learning mode.
2. `autogen.initiate_chats` runs three chats **sequentially**:
   - UserProxyAuto → **DomainResearcher** with the research task; summarized by `reflection_with_llm`.
   - UserProxyAuto → **EnsembleSynthesizer** with the synthesis task (fixed six-section report contract: Introduction, Key Concepts, Real-World Applications, Challenges, Future Trends, Conclusion); the previous chat's summary arrives as carryover.
   - **Critic** → **Writer** (`max_turns: 2`, `summary_method: last_msg`) to refine the draft into the final report.
3. Because the Critic has nested chats registered with `trigger=writer_agent`, the Writer's reply is routed through the five reviewers — each a single turn, each summarized as JSON via `reflection_with_llm`, ending with the MetaReviewer aggregating feedback.
4. The app takes the last message of the last chat, strips the `TERMINATE` sentinel, and renders it with `st.markdown`.
5. Optional free-text feedback triggers one more chat (UserProxyAuto → Critic) asking for adjustments; quiz generation is an independent single chat (UserProxyAuto → QuizGenerator) parameterized by the slider value.

## Orchestration analysis: what is sequential, parallel, async

- **Everything is sequential and synchronous.** `initiate_chats` executes its chat list in order; the nested review chats also run one at a time (`max_turns: 1` each). There is no parallel fan-out and no async execution anywhere in the file.
- **Why this shape:** each stage consumes the previous stage's summary (`carryover` + `clear_history: False`), so ordering is a data dependency for research → synthesis → writing. The five reviewers, by contrast, are mutually independent — their sequential execution is a simplicity choice, not a dependency (see Extending, below).
- **Termination protocol:** agents are instructed to append `TERMINATE`; both `user_proxy_auto` and the Critic detect it with `is_termination_msg` lambdas, and the UI strips it before rendering. `max_turns` caps bound every conversation, so no chat can loop unbounded.
- **The Streamlit cost:** the whole pipeline runs inside one script execution, so the browser blocks until all chats finish. The progress bar is cosmetic — it advances on fixed `time.sleep` calls, not on real pipeline progress.

## State and context engineering

- **Session state:** none persisted. No database, no file writes (other than AutoGen's `work_dir="coding"` if an agent ever emits code), no `st.session_state`. Each form submit is a fresh pipeline run.
- **Context assembly:** context is engineered through three mechanisms — (1) system prompts that pin each agent to a narrow role and to the user-entered topic; (2) task strings that inline the classification taxonomy and learning mode, giving the model domain framing without retrieval; (3) `reflection_with_llm` summaries that compress each stage before it is carried into the next, bounding context growth across the pipeline.
- **Structural contract:** the six-section report format is stated identically in the synthesizer's system prompt and in the synthesis task, and the CompletionReviewer's sole job is to verify those sections exist — the same contract enforced at generation and at review.

## Design decisions and trade-offs visible in the code

- **One shared `llm_config` (gpt-4o) for all ten assistant agents.** Simple and consistent; forgoes cost tiering (reviewers doing 3-bullet checks could run on a cheaper model).
- **Reviewer panel as nested chats rather than pipeline stages.** Keeps the main pipeline three stages long while still attaching multi-dimensional review; the trade-off is that review feedback influences the Writer only within the `max_turns: 2` critic–writer exchange.
- **Prompt-engineered focus instead of retrieval.** The researcher is instructed to cite "working, clickable reference URLs" from model knowledge. This keeps the system dependency-free but makes citation freshness and URL validity unverifiable at generation time.
- **`code_execution_config` with `use_docker=False`** on the user proxy: enables AutoGen's code-execution path without container isolation. Convenient for local experimentation; a hardening liability (see [HARDENING.md](HARDENING.md)).

### Observed limitations (checkable in the file)

- `EnsembleContentAgent.process` indexes the completion as a dict (`result["choices"][0]...`), which does not match the object returned by the `openai>=1.0` client used at the top of the file. The method is only exercised if that code path is invoked; the pipeline's `initiate_chats` route does not call it.
- The quiz button reads `topic_prompt` from the form's widget; generating a quiz before a topic has been entered produces a quiz task with an empty topic.
- The final report is taken from the last message of the last chat; reviewer output is not programmatically merged into it.

## Extending this system

Grounded in what the code already sets up:

1. **Give the researcher a real retrieval tool.** `requirements.txt` already lists `serpapi`/`google-search-results`; registering a search function on DomainResearcher (AutoGen function calling) would turn "include working URLs" from an instruction into a verified capability, and would make the date injected into the research task meaningful.
2. **Parallelize the reviewer panel.** The five reviewers are independent single-turn checks with JSON-shaped outputs; running them concurrently (async `initiate_chats` or plain thread fan-out) would cut wall-clock review time roughly five-fold with no behavioral change, since the MetaReviewer already exists to aggregate.
3. **Persist runs in `st.session_state` and on disk.** The quiz agent is prompted "based on the generated learning report" but never receives it — storing the report in session state and injecting it into the quiz task would make the quiz actually report-grounded, and stored reports enable the follow-up-topics flow the Conclusion section invites.
4. **Tier the models per role.** The shared `llm_config` is a one-line-per-agent change; pointing the five reviewers at a smaller model keeps the Writer/Researcher on `gpt-4o` while cutting the largest token cost in the pipeline (five review chats per run).
5. **Make the learning mode structural.** `learning_mode` currently only decorates the research prompt; mapping it to concrete report parameters (section depth, word budget, quiz length default) would give the "adaptive" in adaptive learning an enforceable meaning.
