# OpenClaw

**AI Agent Control Center** — A unified workspace framework for managing AI agents, memory, skills, and multi-model orchestration.

## What is OpenClaw?

OpenClaw provides a single, coherent environment for building and running AI agents. It brings together:

- **Memory** — Persistent short-term and long-term memory across sessions
- **Skills** — A modular, hot-reloadable skill system with 50+ built-in capabilities
- **Multi-Agent** — Spawn, coordinate, and orchestrate sub-agents with shared context
- **Multi-Model** — Route tasks to the best model for each job (GPT, Claude, Gemini, and more)
- **Heartbeats** — Proactive agent behavior with scheduled awareness checks
- **Sessions** — Context-isolated sessions across chat platforms, CLI, and API

## Documentation

```bash
# Clone and run docs locally
git clone https://github.com/luchun19921229/openclaw.git
cd openclaw
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) to view the docs.

## Architecture

```
┌─────────────────────────────────────────┐
│            OpenClaw Runtime             │
├──────────┬──────────┬──────────────────┤
│ Sessions │ Heartbeat│  Gateway/HTTP    │
├──────────┴──────────┴──────────────────┤
│          Agent Engine (SOUL.md)         │
├────────┬────────┬────────┬─────────────┤
│Memory  │ Skills │ Models │ Sub-Agents  │
├────────┴────────┴────────┴─────────────┤
│     Channel Plugins (WeChat/Discord/…)  │
└─────────────────────────────────────────┘
```

## Key Concepts

### Memory System
Every agent has persistent memory. Short-term memory tracks daily context; long-term memory (`MEMORY.md`) stores curated knowledge. Memory survives restarts.

### Skills
Skills are modular capability packs — each with a `SKILL.md` that the agent reads on demand. Install new skills via the skill marketplace or build your own.

### Multi-Agent Orchestration
Spawn sub-agents for complex tasks. They run in isolated contexts and report results back. Parent agents can steer, monitor, or terminate sub-agents.

### Heartbeats
Agents don't just respond — they act proactively. Heartbeats run periodic checks (email, calendar, weather) and reach out when something needs attention.

## License

MIT
