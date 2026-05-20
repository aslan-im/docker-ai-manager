# Docker AI Manager

An AI-powered DevOps agent for monitoring and managing Docker containers across multiple remote servers. It uses a ReAct (Reason + Act) loop powered by OpenAI's GPT-4o-mini and connects to remote Docker hosts over SSH.

## Features

- **Multi-server support** — manage any number of remote servers defined in `config.yaml`
- **Interactive chat interface** — conversational CLI for natural language commands
- **ReAct reasoning loop** — the agent thinks, acts with tools, observes results, and iterates
- **Human-in-the-loop safety** — destructive actions (e.g. `restart_container`) require explicit approval before execution
- **Structured tool use** — OpenAI function calling with Pydantic-validated arguments

## Available Tools

| Tool | Description |
|---|---|
| `list_containers` | List all containers on a server with status and image |
| `get_container_logs` | Fetch the last N lines of logs from a container |
| `restart_container` | Restart a container (requires human approval) |
| `inspect_container` | Full `docker inspect` output — ports, mounts, network mode, state |
| `check_disk_space` | Run `df -h` on the remote host via a temporary Alpine container |
| `wait` | Pause execution for N seconds (used after restarts before checking logs) |

## Project Structure

```
docker-manager/
├── agent.py          # Entry point — ReAct loop, tool dispatcher, CLI chat
├── tools.py          # RemoteDockerManager class (SSH + Docker SDK)
├── tools_schema.py   # Pydantic models and OpenAI function-calling schemas
├── config.yaml       # Server definitions (gitignored)
├── config.yaml.example
└── pyproject.toml
```

## Setup

**Prerequisites:** Python 3.14+, [`uv`](https://github.com/astral-sh/uv), SSH access to your remote servers, and Docker running on those servers.

**1. Clone and install dependencies**

```bash
git clone <repo-url>
cd docker-manager
uv sync
```

**2. Configure servers**

```bash
cp config.yaml.example config.yaml
```

Edit `config.yaml` to match your servers:

```yaml
servers:
  - name: srv1
    host: 192.168.0.19
    username: admin
    key_filename: ~/.ssh/id_ed25519
  - name: raspi
    host: 192.168.0.20
    username: pi
    key_filename: ~/.ssh/id_ed25519
```

**3. Set your OpenAI API key**

Create a `.env` file in the project root:

```
API_KEY=sk-...
```

**4. Run**

```bash
uv run agent.py
```

## Usage

Once running, type natural language commands. The agent gathers information before acting and always asks for confirmation before restarting containers.

```
👤 You: check all containers on raspi
👤 You: get the last 50 lines of logs for nginx on srv1
👤 You: is the disk on srv1 getting full?
👤 You: restart the plex container on srv1
```

Type `exit` or `quit` to end the session, or press `Ctrl+C`.

## How It Works

1. Your message is appended to a persistent session history
2. The agent calls the OpenAI API with the full history and available tool schemas
3. If the model requests a tool call, the dispatcher validates arguments with Pydantic and executes the corresponding `RemoteDockerManager` method over SSH
4. The tool result is appended to the history and the loop repeats until the model returns a final text response
5. State-changing tool calls (`restart_container`) are intercepted and require `y` confirmation in the terminal before proceeding

## Dependencies

- [`docker[ssh]`](https://docker-py.readthedocs.io/) — Docker SDK for Python; the `[ssh]` extra pulls in `paramiko` which is required for SSH transport (`ssh://` URLs)
- [`openai`](https://github.com/openai/openai-python) — OpenAI API client
- [`pydantic`](https://docs.pydantic.dev/) — argument validation for tool calls
- [`python-dotenv`](https://github.com/theskumar/python-dotenv) — `.env` file loading
- [`pyyaml`](https://pyyaml.org/) — `config.yaml` parsing
