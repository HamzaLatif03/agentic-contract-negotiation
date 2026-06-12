# Agentic Contract Negotiation

Automated multi-agent loan contract negotiation using **Microsoft AutoGen** and **Llama** models served via a remote **Ollama** instance.

## Prerequisites

- [Conda](https://docs.conda.io/en/latest/miniconda.html)
- A remote Ollama server with a Llama model pulled (e.g. `ollama pull llama3.1:8b`)

## Setup

```bash
conda env create -f environment.yml
conda activate loan-negotiation
cp .env.example .env   # set OLLAMA_BASE_URL and OLLAMA_MODEL
loan-negotiate status
```

## Project layout

```
src/loan_negotiation/
├── config.py              # OLLAMA_BASE_URL, MODEL, MAX_ROUNDS
├── models/
│   ├── loan_terms.py      # BorrowerTerms, LenderTerms, DealTerms
│   ├── negotiation.py     # RoundOffer, NegotiationState
│   └── workflow.py        # WorkflowResult, ReviewFeedback, Scores
├── services/
│   ├── feasibility.py     # Deterministic impossible-deal detection
│   └── fairness.py        # Score-balance logic
├── agents/
│   ├── factory.py         # Builds all AssistantAgents + model client
│   ├── intake.py
│   ├── negotiators.py
│   ├── rankers.py
│   └── reviewer.py
├── workflow/
│   ├── orchestrator.py    # Main state machine (UI-agnostic)
│   └── prompts.py         # System prompts per agent role
└── cli/
    └── main.py            # Typer commands: run, status
```

## CLI commands

| Command | Description |
|---------|-------------|
| `loan-negotiate status` | Verify Ollama connection and show config |
| `loan-negotiate run` | Run negotiation workflow (in progress) |

## Configuration

| Variable | Description |
|----------|-------------|
| `OLLAMA_BASE_URL` | Remote Ollama base URL |
| `OLLAMA_MODEL` | Model name on the server |
| `MAX_NEGOTIATION_ROUNDS` | Negotiation round limit (default: 10) |

## Dependencies

Runtime and dev dependencies are listed explicitly in [`environment.yml`](environment.yml) for conda, and in [`pyproject.toml`](pyproject.toml) for pip packaging. Keep both in sync when adding new packages.

To update an existing environment after changing dependencies:

```bash
conda env update -f environment.yml --prune
```
