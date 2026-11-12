# ADR-0001: Tech-Stack und LLM-Anbieterstrategie

🇬🇧 [English](0001-tech-stack-and-llm.md) · 🇩🇪 Deutsch

- **Status:** angenommen
- **Datum:** 2026-11-12
- **Issue:** #1

## Kontext

agentic-pm braucht eine Implementierungssprache für Adapterschicht, Reasoning-Engine und Schnittstellenschicht. Außerdem braucht es einen Weg, ein Sprachmodell für Schlussfolgerungen, Zusammenfassungen und Wissensextraktion aufzurufen.

Anforderungen, die die Wahl prägen:

- Sprach- und NLP-Werkzeuge (Transkription, Sprach-Pipelines) sind ab Phase 3 zentral.
- Das Model Context Protocol (MCP) ist eine zentrale Integrationsschnittstelle.
- Teams müssen das System betreiben können, **ohne Projektdaten an einen externen Modellanbieter zu senden**. Gespräche, Tickets und Sprachtranskripte sind sensibel (siehe [Leitplanken](../de/guardrails.md)).
- Der Stack soll uns nicht an einen Modellanbieter binden.

## Entscheidung

### Sprache & Werkzeuge

| Thema | Wahl |
|-------|------|
| Sprache | **Python ≥ 3.12** |
| Paketierung / Umgebung | `uv` + `pyproject.toml` (src-Layout, Paket `agentic_pm`) |
| Datenmodelle & Validierung | Pydantic v2 |
| Konfigurationsformat | YAML (`.agent-pm/team.yaml`) mit veröffentlichtem JSON-Schema |
| MCP | Offizielles `mcp`-Python-SDK v2 (`MCPServer`) |
| HTTP-Client | `httpx` (async) |
| Qualität | `ruff` (Lint + Format), `mypy --strict`, `pytest` |
| CI | GitHub Actions |

Die Web-Steuerungsoberfläche (Phase 2) wird serverseitig aus demselben Python-Dienst gerendert (z. B. FastAPI + HTMX), damit wir bei einer Sprache bleiben. Diese Wahl bekommt ein eigenes ADR.

### LLM-Strategie: anbieterunabhängig, lokal zuerst

1. Jeder Modellzugriff läuft über eine interne Schnittstelle, `LLMProvider` (`agentic_pm.llm`). Kein anderes Modul importiert ein Anbieter-SDK.
2. Das **Standard-Backend ist ein selbst gehostetes lokales Modell**, angesprochen über die OpenAI-kompatible HTTP-API, die Ollama, vLLM, llama.cpp-Server und LM Studio bereitstellen. Die Daten bleiben auf Infrastruktur, die die Organisation selbst kontrolliert.
3. Gehostete Anbieter (z. B. Anthropic, Azure, Bedrock) können später als optionale Plug-ins hinter derselben Schnittstelle ergänzt werden. Sie werden als Extras installiert und pro Installation aktiviert, nie standardmäßig.
4. Die Modellwahl ist Konfiguration (`llm.provider`, `llm.model`, `llm.base_url`), kein Code.
5. Prompts und Werkzeugdefinitionen bleiben anbieterneutral. Jede Anbieterklasse kümmert sich um anbieterspezifische Details.

## Konsequenzen

- ✅ Läuft vollständig on-premises. Das stützt die Datenschutzzusagen und vermeidet Kosten pro Token.
- ✅ Ein Modellwechsel (größeres lokales Modell oder ein gehostetes für einen Pilot) ist eine Konfigurationsänderung.
- ✅ Python bietet direkten Zugang zu Sprachwerkzeugen (z. B. Whisper-Varianten) für Phase 3.
- ⚠️ Lokale Modelle sind bei komplexem Schlussfolgern schwächer als führende gehostete Modelle. Die Engine muss mit kleineren Modellen funktionieren: kleine, fokussierte Prompts, strukturierte (JSON-)Ausgabe, deterministische Graphlogik im Code statt im Modell.
- ⚠️ Wir brauchen pro Schleife einen Evaluationsdatensatz, um Modellwechsel vergleichen zu können (als Folgeaufgabe erfasst).
- ⚠️ Betreiber müssen GPU-/CPU-Kapazität für das lokale Modell bereitstellen. Hardware-Dimensionierung gehört in die Deployment-Doku.
