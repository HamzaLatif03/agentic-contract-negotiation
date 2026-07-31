# Agentic Contract Negotiation

Automated multi-agent loan contract negotiation using **Microsoft AutoGen**, with comparison models via **cloud APIs** (Gemini, Groq, OpenRouter) and optional local **Ollama**.

## Prerequisites

- [Conda](https://docs.conda.io/en/latest/miniconda.html)
- API keys for the models you want to compare (see `.env.example`)
- Optional: [Ollama](https://ollama.com/download) only if you use **Local Ollama**

## Setup

```bash
conda env create -f environment.yml
conda activate loan-negotiation
cp .env.example .env
# Edit .env and set GOOGLE_API_KEY, GROQ_API_KEY, OPENROUTER_API_KEY
pip install -e .
```

## Project layout

```
src/loan_negotiation/
├── config.py              # API keys, OLLAMA_BASE_URL, MODEL, MAX_ROUNDS
├── models/
│   ├── loan_terms.py      # BorrowerTerms, LenderTerms, DealTerms
│   └── workflow.py        # WorkflowResult, ReviewFeedback, Scores
├── services/
│   ├── feasibility.py     # Deterministic impossible-deal detection
│   ├── fairness.py        # Score-balance logic
│   ├── deal_scoring.py    # Deterministic party scores
│   └── model_catalog.py   # Comparison model switcher
├── agents/
│   ├── factory.py         # Model client + AssistantAgent builder
│   ├── intake.py
│   └── reviewer.py
├── workflow/
│   ├── orchestrator.py    # Main state machine (UI-agnostic)
│   └── prompts.py         # System prompts per agent role
├── api/
│   ├── main.py            # FastAPI + SSE for web UI
│   ├── schemas.py
│   └── serialize.py
└── cli/
    ├── main.py            # Entry point
    └── intake.py          # Interactive term collection
frontend/                  # React + Tailwind (Vite)
```

## Usage

### CLI

```bash
loan-negotiate          # enter your own borrower and lender terms
loan-negotiate --demo   # quick test with sample data
```

### Web UI (local)

Start the API and React dev server in two terminals:

```bash
# Terminal 1 — API (loads keys from .env)
conda activate loan-negotiation
loan-negotiate-api

# Terminal 2 — frontend
cd frontend
echo 'API_PROXY_TARGET=http://127.0.0.1:8000' > .env.local
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173). Vite proxies `/api` to `http://127.0.0.1:8000`.

Optionally upload a **lender opening offer PDF**. The API extracts downpayment, rate, term, and fixed/variable structure, then seeds negotiation so the **borrower counters first**.

Use the **Comparison models** picker:

| Model | Provider |
|-------|----------|
| Gemini 3.1 Flash Lite | Google API (`GOOGLE_API_KEY`) |
| Groq Llama 3.3 70B | Groq (`GROQ_API_KEY`) |
| GPT-OSS 20B / Nemotron Nano 30B / Nemotron Super 120B | OpenRouter **free** (`OPENROUTER_API_KEY`, ids end in `:free`) |
| Local Ollama | Optional local Ollama |

Put keys in **`.env`** (never commit them). Refresh the picker after restarting the API.

Each completed run reports **LLM run metrics** in the outcome panel: tokens, time to first model output, and total workflow duration.

Agent messages print live in the feed as each stage runs (`negotiation`, `ranking`, etc.).

Set `MAX_NEGOTIATION_ROUNDS=2` in `.env` for faster runs while testing.

## CLI commands

| Command | Description |
|---------|-------------|
| `loan-negotiate` | Interactive intake, then full agent workflow |
| `loan-negotiate --demo` | Run with built-in sample borrower/lender data |
| `loan-negotiate-api` | Start FastAPI server for the web UI |

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `GOOGLE_API_KEY` / `GEMINI_API_KEY` | Google Gemini API key | unset |
| `GROQ_API_KEY` | Groq API key | unset |
| `OPENROUTER_API_KEY` / `LLAMA_API_KEY` | OpenRouter key (free Llama route) | unset |
| `OLLAMA_MODEL` | Default catalog model id (overridable per run in the UI) | `gemini-3.1-flash-lite` |
| `OLLAMA_BASE_URL` | Local Ollama URL (optional) | `http://localhost:11434` |
| `OLLAMA_NUM_GPU` | Ollama GPU layers when using local Ollama | unset / auto |
| `MAX_NEGOTIATION_ROUNDS` | Negotiation round limit per attempt | `10` |
| `MAX_FAIRNESS_ADJUSTMENTS` | Max fairness nudges when score gap > 2 | `5` |

## Workflow outcomes

| Status | Meaning |
|--------|---------|
| `approved` | Consensus deal, valid ranges, score gap ≤ 2 |
| `rejected` | Deal found but unfair (gap > 2) or out of range |
| `no_deal` | Negotiation ended without a usable agreement |
| `impossible` | Opening ranges do not overlap |
| `in_progress` | Live UI only — run still streaming |

## Dependencies

Runtime and dev dependencies are listed in [`environment.yml`](environment.yml) and [`pyproject.toml`](pyproject.toml). Keep both in sync when adding packages.

```bash
conda env update -f environment.yml --prune
```
