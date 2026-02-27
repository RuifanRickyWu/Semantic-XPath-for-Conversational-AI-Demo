## Semantic XPath Chat: Structured Agentic Memory Demo

**Semantic XPath Chat** is an end-to-end conversational AI demo that showcases **SEMANTIC XPath**, a structure-aware retrieval and editing method for long-term, task-oriented interactions over hierarchical memories.

The demo implements the full pipeline described in the paper: user requests are translated into SEMANTIC XPath queries, evaluated over a tree-structured task memory, and the retrieved substructures are used to generate grounded model responses while visualizing memory and query execution.


## System Overview

Semantic XPath Chat consists of:

- **Backend (`Semantic_Xpath_BE/`)**
  - Maintains **tree-structured task memory** (e.g., itinerary → days → activities, to‑do list → sections → items).
  - Parses user requests into **SEMANTIC XPath** queries using LLM prompts.
  - Executes queries via a **structure-aware evaluator** with semantic scoring (similarity or entailment) as described in Appendix A of the paper  .
  - Orchestrates intent handling, query generation, predicate scoring, result verification, and memory updates.
  - Exposes an HTTP API and a simple CLI.

- **Frontend (`Semantic_Xpath_FE/`)**
  - React + TypeScript + Vite single-page app.
  - **Conversation view**: shows the dialogue between user and assistant.
  - **Memory view**: visualizes the current structured memory (e.g., itinerary tree) with the **queried path highlighted**.
  - **Execution details view**: surfaces the generated SEMANTIC XPath query, intermediate node scores, and retrieved subtrees (corresponding to Figures 2–3 in the paper).

---

## Repository Layout

- **Top level**
  - `Semantic_Xpath_BE/` – Python backend (Flask app + orchestrator + semantic XPath engine).
  - `Semantic_Xpath_FE/` – React frontend for the chat and visualization UI.
  - `LICENSE` – License for this demo.

- **Backend (`Semantic_Xpath_BE/`)**
  - `run.py` – Flask application entry point.
  - `app_factory.py` – Creates and wires the Flask app and core components.
  - `config.yaml` – Configuration for semantic scoring and OpenAI / entailment backends.
  - `api/` – HTTP resources (chat API, etc.).
  - `interfaces/`, `services/`, `stores/` – Orchestration, session & context management, intent handling, and state persistence.
  - `domain/semantic_xpath/` – Core SEMANTIC XPath engine:
    - `parsing/` – Parser and AST for the SEMANTIC XPath language.
    - `execution/` – Structural operators, semantic relevance operators, and execution pipeline (as in Appendix A  ).
    - `node_ops.py` – Node utilities and tree operations.
  - `storage/templates/` – Template XML/JSON task structures used to bootstrap tasks (itineraries, to-do lists, meal kits).
  - `cli_orchestrator.py` – Text-based CLI for running the demo without the web UI.

- **Frontend (`Semantic_Xpath_FE/`)**
  - `src/App.tsx`, `src/pages/`, `src/components/` – Main UI components (chat panel, memory tree, execution details).
  - `src/api/` – API client; `apiBase.ts` points to the backend (defaults to `http://localhost:5001/api`).
  - `public/` – Static assets and icons for the demo.

---

## Prerequisites

- **Backend**
  - Python **3.9+**
  - `OPENAI_API_KEY` set in the environment (used via `config.yaml` under the `openai` section).
  - (Optional) **Modal / local entailment model configuration** if using entailment-based scoring (default in `config.yaml` is `scoring_method: "entailment"` with a Modal BART worker).

- **Frontend**
  - Node.js **18+** and npm.

---

## Backend Setup and Usage

### Install dependencies

From the repository root:

```bash
cd Semantic_Xpath_BE
pip install -r requirements.txt
```

Ensure `OPENAI_API_KEY` is available:

```bash
export OPENAI_API_KEY="your-key-here"
```

If you use the default entailment-based scorer backed by Modal, also configure your Modal credentials and environment to match `config.yaml` (section `entailment.modal`).

### Run the Flask API server

```bash
cd Semantic_Xpath_BE
python run.py
```

By default this starts the backend at `http://0.0.0.0:5001` with the API under `/api`.

### Run the CLI (optional, non-UI demo)

You can interact with the orchestrator via a simple text-only CLI:

- **Interactive mode**

  ```bash
  cd Semantic_Xpath_BE
  python cli_orchestrator.py
  ```

  You will see a prompt like `you[cli-default]>`. Type a request (e.g., “Create a 3‑day ACL 2026 trip plan in San Diego”) and press Enter. Type `q`, `quit`, `exit`, or `e` to leave the session.

- **Single-message mode**

  ```bash
  cd Semantic_Xpath_BE
  python cli_orchestrator.py --message "Create a 5-day GRE prep plan"
  ```

- **Common options**

  - `--session-id <id>` – Use or create a named session for long-term interaction.
  - `--message <text>` – Run one turn with this message and then exit.
  - `--json` – Return raw `TurnResponse` JSON instead of rendered assistant text.

- **In-session commands**

  - `q`, `e`, `quit`, `exit` – Quit the CLI.
  - `r`, `reset` – Clear all memory, plans, tasks, and XML data for the current session.
  - `/session <id>` – Switch to a different session.
  - `/help` – Show command help.

---

## Frontend Setup and Usage

### Install dependencies

From the repository root:

```bash
cd Semantic_Xpath_FE
npm install
```

### Configure backend URL (optional)

By default, the frontend talks to `http://localhost:5001/api` (see `src/api/apiBase.ts`). To point to a different backend origin (e.g., a remote demo server), set:

```bash
export VITE_API_URL="https://your-backend-origin"
```

The code will convert this origin into an `/api` base path automatically.

### Run the dev server

```bash
cd Semantic_Xpath_FE
npm run dev
```

Open the printed localhost URL (typically `http://localhost:5173`) in a browser.

---

## Using the Demo

1. **Start a new task** by prompting the assistant, e.g.:
   - “Create a 3-day ACL 2026 conference itinerary in San Diego.”
   - “Create a weekly to-do list for preparing an ACL submission.”
   - “Recommend a 5-day vegetarian meal kit plan.”
2. **Issue structure-aware requests**, such as:
   - “Add a coffee break on the day that is packed with conference sessions.”
   - “Move the poster session to the day with the fewest talks.”
   - “For the meal kit plan, replace the spiciest dinner with something milder.”
3. **Inspect the memory view** to see the hierarchical structure (days, items, versions) and the highlighted nodes affected by the current SEMANTIC XPath query.
4. **Open the execution details panel** to view:
   - The **generated SEMANTIC XPath query**.
   - Intermediate structural matches and semantic scores over candidate nodes.
   - The final retrieved subtrees used for answer generation.

This end-to-end experience mirrors Figures 2–3 in the paper and highlights how SEMANTIC XPath retrieves and edits the right substructure with far fewer tokens than in-context baselines  .