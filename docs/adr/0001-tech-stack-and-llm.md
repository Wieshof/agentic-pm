# ADR-0001: Tech stack and LLM provider strategy

🇬🇧 English · 🇩🇪 [Deutsch](0001-tech-stack-and-llm.de.md)

- **Status:** accepted
- **Date:** 2026-11-12
- **Issue:** #1

## Context

agentic-pm needs one implementation language for the adapter layer, reasoning engine and interface layer. It also needs a way to call a language model for reasoning, summarising and knowledge extraction.

Requirements that shape the choice:

- Speech and NLP tooling (transcription, voice pipelines) is central from Phase 3 onward.
- The Model Context Protocol (MCP) is a first-class integration surface.
- Teams must be able to run the system **without sending project data to a third-party model provider**. Conversations, tickets and voice transcripts are sensitive (see [guardrails](../guardrails.md)).
- The stack should not lock us into one model vendor.

## Decision

### Language & tooling

| Concern | Choice |
|---------|--------|
| Language | **Python ≥ 3.12** |
| Packaging / env | `uv` + `pyproject.toml` (src layout, package `agentic_pm`) |
| Data models & validation | Pydantic v2 |
| Config format | YAML (`.agent-pm/team.yaml`) with a published JSON Schema |
| MCP | Official `mcp` Python SDK v2 (`MCPServer`) |
| HTTP client | `httpx` (async) |
| Quality | `ruff` (lint + format), `mypy --strict`, `pytest` |
| CI | GitHub Actions |

The web control plane (Phase 2) will be server-rendered from the same Python service (e.g. FastAPI + HTMX) so we keep a single language. That choice will get its own ADR.

### LLM strategy: provider-agnostic, local-first

1. All model access goes through one internal interface, `LLMProvider` (`agentic_pm.llm`). No other module imports a vendor SDK.
2. The **default backend is a self-hosted local model** reached through the OpenAI-compatible HTTP API that Ollama, vLLM, llama.cpp server and LM Studio all expose. Data stays on infrastructure the organisation controls.
3. Hosted providers (e.g. Anthropic, Azure, Bedrock) can be added later as optional plug-ins behind the same interface. They are installed as extras and enabled per deployment, never by default.
4. Model choice is configuration (`llm.provider`, `llm.model`, `llm.base_url`), not code.
5. Prompts and tool definitions are kept provider-neutral. Each provider class handles provider-specific details.

## Consequences

- ✅ Runs fully on-premises. This supports the privacy guarantees and avoids per-token costs.
- ✅ Swapping models (bigger local model, or a hosted one for a pilot) is a config change.
- ✅ Python gives direct access to speech tooling (e.g. Whisper variants) for Phase 3.
- ⚠️ Local models are weaker than frontier hosted models at complex reasoning. The engine must work with smaller models: small focused prompts, structured (JSON) output, deterministic graph logic in code rather than in the model.
- ⚠️ We need an evaluation set per loop so model changes can be compared (tracked as a follow-up).
- ⚠️ Operators must provide GPU/CPU capacity for the local model. Hardware sizing goes in the deployment docs.
