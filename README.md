# Agentic Contract Negotiation

Multi-agent **UK mortgage** negotiation with [Microsoft AutoGen](https://microsoft.github.io/autogen/). Borrower and lender agents bargain over deposit, rate, term, fees, and related terms. A middleman closes score gaps when needed; hard walls and deterministic scoring keep deals feasible and fair.

The live comparison set is exactly **three** models:

| Model | Runtime | Credential |
|-------|---------|------------|
| **Llama 3.2** | Local [Ollama](https://ollama.com/download) (`llama3.2:latest`) | Ollama running at `OLLAMA_BASE_URL` |
| **Gemini 3.1 Flash Lite** | Google API | `GOOGLE_API_KEY` or `GEMINI_API_KEY` |
| **Mistral Small** | Mistral API | `MISTRAL_API_KEY` |

Run from the **CLI** or a **React** web UI with a live agent feed, curated personas, and optional lender PDF opening offers.

## How it works

1. **Feasibility** — Reject deals whose hard ranges never overlap.
2. **Negotiation** — Borrower and lender agents exchange structured offers (up to `MAX_NEGOTIATION_ROUNDS`).
3. **Middleman** — If needed, a fairness agent irons a package so both party scores sit within a small gap.
4. **Ratification** — Each side accepts or rejects once; hard numeric walls still apply.
5. **Outcome** — Status, scores, deal terms, and LLM metrics (tokens, latency) are returned and appended under `results/`.

Optional PDF upload: text is extracted from the file, then **local Llama 3.2** always builds the structured opening offer. The selected comparison model continues the bargain so the **borrower counters first**.

## Prerequisites

- [Conda](https://docs.conda.io/en/latest/miniconda.html) (Python 3.11)
- API keys for Gemini and/or Mistral (see `.env.example`)
- [Node.js](https://nodejs.org/) 18+ for the web UI
- Optional: Ollama with `ollama pull llama3.2` for the local comparison model and PDF opening-offer extraction

## Setup

```bash
conda env create -f environment.yml
conda activate loan-negotiation
cp .env.example .env
# Edit .env — set GOOGLE_API_KEY and/or MISTRAL_API_KEY
```

The conda env installs the package in editable mode (`pip install -e .`).

## Run

### CLI

```bash
conda activate loan-negotiation
loan-negotiate                          # interactive borrower / lender intake
loan-negotiate --demo                   # demo persona terms
loan-negotiate --persona features-duel  # named persona from the catalog
loan-negotiate --model mistral-small    # pick one of the three comparison models
```

### Web UI

Two terminals:

```bash
# Terminal 1 — API
conda activate loan-negotiation
loan-negotiate-api

# Terminal 2 — frontend
cd frontend
echo 'API_PROXY_TARGET=http://127.0.0.1:8000' > .env.local
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173). Vite proxies `/api` to the FastAPI server on port 8000.

In the UI you can choose one of the three comparison models, a persona pair, optionally upload a lender offer PDF, and watch stages stream live.

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `GOOGLE_API_KEY` / `GEMINI_API_KEY` | Gemini API key | unset |
| `MISTRAL_API_KEY` | Mistral API key | unset |
| `OLLAMA_MODEL` | Default catalog id (`ollama-local`, `gemini-3.1-flash-lite`, or `mistral-small`) | `gemini-3.1-flash-lite` |
| `OLLAMA_BASE_URL` | Local Ollama URL | `http://localhost:11434` |
| `MAX_NEGOTIATION_ROUNDS` | Round limit per negotiation | `10` |
| `MAX_FAIRNESS_ADJUSTMENTS` | Max silent fairness nudges when score gap > 2 | `3` |

Put keys in **`.env`** only — never commit them. Restart the API after changing keys. Use a lower `MAX_NEGOTIATION_ROUNDS` (for example `2`) for faster smoke tests.

## Outcomes

| Status | Meaning |
|--------|---------|
| `approved` | Consensus deal, valid ranges, score gap ≤ 2 |
| `rejected` | Deal found but unfair or out of range |
| `no_deal` | No usable agreement |
| `impossible` | Opening ranges do not overlap |
| `in_progress` | Live UI only — run still streaming |

Completed runs append to `results/interactions.json`.

## Analysis plots

```bash
conda activate loan-negotiation
python analysis/plot_interactions.py
```

Figures and `summary_by_model.csv` go to `analysis/figures/` (gitignored; regenerate anytime)..

## Tests

```bash
conda activate loan-negotiation
pytest
```

## Project layout

```
src/loan_negotiation/
├── api/           # FastAPI + SSE for the web UI
├── agents/        # Model clients and AutoGen agents
├── cli/           # Typer CLI entry points
├── models/        # Loan terms and workflow result types
├── services/      # Feasibility, scoring, fairness, PDF extract, catalog
└── workflow/      # Orchestrator, prompts, personas, deal parsing
frontend/          # React + Vite + Tailwind UI
analysis/          # Plot script (figures regenerated locally)
results/           # Interaction logs
tests/
```

## Commands

| Command | Description |
|---------|-------------|
| `loan-negotiate` | Interactive CLI negotiation |
| `loan-negotiate --demo` | Demo terms |
| `loan-negotiate --persona <id>` | Run a named persona |
| `loan-negotiate --model <id>` | Force one of the three comparison models |
| `loan-negotiate-api` | Start the API for the web UI |

Dependencies live in [`environment.yml`](environment.yml) and [`pyproject.toml`](pyproject.toml). After dependency changes:

```bash
conda env update -f environment.yml --prune
```
