# mini-agent

A minimal AI coding agent: an LLM ↔ shell loop with linear history, structured
observations, trajectory logging, and pluggable execution backends (local shell
or Docker sandbox).

## Setup

Requires [uv](https://docs.astral.sh/uv/) and Python 3.12+.

```bash
git clone git@github.com:haibian2604-del/mini-agent.git
cd mini-agent
uv sync
```

Configure credentials in `.env` (behavior config lives in `src/mini_agent/config/default.yaml`):

```bash
cp .env.example .env   # then fill in your key
```

```dotenv
API_KEY=your-key
BASE_URL=https://openai-compatible-endpoint/v4   # leave empty for official OpenAI
```

## Quickstart

```bash
cp .env.example .env   # fill in API_KEY (BASE_URL if not official OpenAI)
uv run mini-agent run "echo hello"
```

The shipped `src/mini_agent/config/default.yaml` points at a custom endpoint
(`openai/glm-5.3-flash`). Using another provider? Either pass a flag:

```bash
uv run mini-agent run --model openai/gpt-4o-mini "echo hello"
```

or edit the `model:` line in the yaml. The name must carry a litellm provider
prefix (`openai/...` = any OpenAI-compatible endpoint, paired with `BASE_URL`).

## Usage

```bash
# one task (local shell)
uv run mini-agent run "在 /tmp/demo 创建 fizzbuzz.py 并运行验证"

# sandboxed in Docker (files persist to ./workspace)
uv run mini-agent run --env docker "在 /workspace 创建 hello.py 并运行"

# interactive mode
uv run mini-agent

# replay a trajectory
uv run mini-agent inspect trajectories/20261025-170943.json
```

Options: `--env local|docker`, `--model provider/name`, `--config path.yaml`,
`--max-steps N`. Priority: CLI > yaml > built-in defaults.

## Development

```bash
uv run pytest -v        # all offline (fake model / fake env)
```

Architecture: `agents/default.py` (the loop) orchestrates two duck-typed
contracts — `model` (`.chat()` / `.parse_action()`) and `env` (`.execute()`).
UI concerns (typer/rich) live only in `run.py`.
