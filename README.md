# Semantic XPath for Conversational AI

A conversational planning system that uses semantic XPath to query and edit structured plans (e.g., study plans, travel itineraries).

## Prerequisites

- Python 3.9+
- `OPENAI_API_KEY` set in your environment or in a `.env` file under `Semantic_Xpath_BE/`

## Running the CLI

The CLI lets you interact with the orchestrator via text. Run it from the `Semantic_Xpath_BE` directory.

### Interactive mode

Start an interactive session:

```bash
cd Semantic_Xpath_BE
python cli_orchestrator.py
```

You'll see a prompt like `you[cli-default]> `. Type your request and press Enter. The assistant will respond. Type `q`, `quit`, `exit`, or `e` to quit.

### Single message mode

Run one turn and exit:

```bash
cd Semantic_Xpath_BE
python cli_orchestrator.py --message "Create a 5-day GRE prep plan"
```

### Options

| Option | Description |
|--------|-------------|
| `--session-id <id>` | Session ID for context continuity (default: `cli-default`) |
| `--message <text>` | Run one turn with this message and exit |
| `--json` | Output raw `TurnResponse` as JSON instead of assistant text |

### In-session commands

While in interactive mode:

| Command | Description |
|---------|-------------|
| `q`, `e`, `quit`, `exit` | Quit the CLI |
| `r`, `reset` | Clear all memory, plans, tasks, and XML data |
| `/session <id>` | Switch to a different session |
| `/help` | Show command help |
