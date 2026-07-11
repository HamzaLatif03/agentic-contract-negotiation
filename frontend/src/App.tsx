import { useCallback, useEffect, useState } from "react";
import {
  checkHealth,
  defaultBorrowerTerms,
  defaultLenderTerms,
  fetchDemoTerms,
  fetchModels,
  parseOfferPdf,
  streamNegotiation,
} from "./api";
import ContractUpload from "./components/ContractUpload";
import LiveFeed from "./components/LiveFeed";
import ModelPicker from "./components/ModelPicker";
import ResultPanel from "./components/ResultPanel";
import TermsForm from "./components/TermsForm";
import { applyFeedEventToResult } from "./dealParse";
import type { BorrowerTerms, DealTerms, FeedEvent, LenderTerms, WorkflowResult } from "./types";

let eventCounter = 0;

export default function App() {
  const [borrower, setBorrower] = useState<BorrowerTerms>(defaultBorrowerTerms);
  const [lender, setLender] = useState<LenderTerms>(defaultLenderTerms);
  const [openingOffer, setOpeningOffer] = useState<DealTerms | null>(null);
  const [offerFilename, setOfferFilename] = useState<string | null>(null);
  const [parseBusy, setParseBusy] = useState(false);
  const [parseError, setParseError] = useState<string | null>(null);
  const [catalog, setCatalog] = useState<
    Array<{
      id: string;
      label: string;
      ollama_name?: string;
      description: string;
      available: boolean;
      resolved_name: string;
      runtime?: "api" | "ollama";
    }>
  >([]);
  const [defaultModel, setDefaultModel] = useState<string | null>(null);
  const [selectedModel, setSelectedModel] = useState("llama3.3:70b");
  const [modelsLoading, setModelsLoading] = useState(false);
  const [modelsError, setModelsError] = useState<string | null>(null);
  const [events, setEvents] = useState<FeedEvent[]>([]);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<WorkflowResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [apiOnline, setApiOnline] = useState<boolean | null>(null);

  const loadModels = useCallback(async () => {
    setModelsLoading(true);
    setModelsError(null);
    try {
      const data = await fetchModels();
      setCatalog(data.catalog);
      setDefaultModel(data.default);
      setSelectedModel((current) => {
        const availableNames = data.catalog
          .filter((row) => row.available)
          .flatMap((row) => [row.resolved_name, row.id]);
        if (availableNames.includes(current)) {
          const match = data.catalog.find(
            (row) => row.resolved_name === current || row.id === current,
          );
          return match?.resolved_name ?? current;
        }
        return data.default;
      });
    } catch (err) {
      setModelsError(err instanceof Error ? err.message : String(err));
    } finally {
      setModelsLoading(false);
    }
  }, []);

  useEffect(() => {
    checkHealth().then(setApiOnline);
    void loadModels();
  }, [loadModels]);

  const loadDemo = useCallback(async () => {
    const demo = await fetchDemoTerms();
    setBorrower(demo.borrower);
    setLender(demo.lender);
    setError(null);
  }, []);

  const handlePdfUpload = useCallback(async (file: File) => {
    setParseBusy(true);
    setParseError(null);
    try {
      const parsed = await parseOfferPdf(file);
      setOpeningOffer(parsed.opening_offer);
      setOfferFilename(parsed.source_filename);
    } catch (err) {
      setOpeningOffer(null);
      setOfferFilename(null);
      setParseError(err instanceof Error ? err.message : String(err));
    } finally {
      setParseBusy(false);
    }
  }, []);

  const startNegotiation = useCallback(() => {
    setRunning(true);
    setEvents([]);
    setResult(null);
    setError(null);

    const cancel = streamNegotiation(
      {
        borrower,
        lender,
        opening_offer: openingOffer,
        llm_model: selectedModel,
      },
      (message) => {
        if (message.type === "event" && message.stage && message.output) {
          setEvents((prev) => [
            ...prev,
            {
              id: `evt-${++eventCounter}`,
              stage: message.stage!,
              agent: message.agent ?? "system",
              output: message.output!,
              timestamp: Date.now(),
            },
          ]);
          setResult((prev) =>
            applyFeedEventToResult(
              prev,
              message.stage!,
              message.agent ?? "system",
              message.output!,
            ),
          );
        }
        if (message.type === "complete" && message.result) {
          setResult(message.result);
        }
        if (message.type === "error") {
          setError(message.message ?? "Unknown error");
        }
      },
      (err) => setError(err.message),
      () => setRunning(false),
    );

    return cancel;
  }, [borrower, lender, openingOffer, selectedModel]);

  const handleSubmit = () => {
    startNegotiation();
  };

  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-4 sm:px-6">
          <div>
            <p className="text-xs font-medium uppercase tracking-widest text-teal-600">
              Agentic negotiation
            </p>
            <h1 className="text-lg font-semibold text-slate-900">Loan contract desk</h1>
          </div>
          <div className="flex items-center gap-2 text-xs text-slate-500">
            <span
              className={`h-2 w-2 rounded-full ${
                apiOnline === null
                  ? "bg-slate-300"
                  : apiOnline
                    ? "bg-emerald-500"
                    : "bg-red-500"
              }`}
            />
            API {apiOnline === null ? "checking…" : apiOnline ? "online" : "offline"}
          </div>
        </div>
      </header>

      <main className="mx-auto grid max-w-7xl gap-6 px-4 py-6 lg:grid-cols-[1fr_380px] sm:px-6">
        <div className="space-y-6">
          <ModelPicker
            catalog={catalog}
            selected={selectedModel}
            defaultModel={defaultModel}
            disabled={running}
            loading={modelsLoading}
            error={modelsError}
            onChange={setSelectedModel}
            onRefresh={() => void loadModels()}
          />
          <ContractUpload
            openingOffer={openingOffer}
            sourceFilename={offerFilename}
            disabled={running}
            busy={parseBusy}
            error={parseError}
            onUpload={handlePdfUpload}
            onClear={() => {
              setOpeningOffer(null);
              setOfferFilename(null);
              setParseError(null);
            }}
          />
          <TermsForm
            borrower={borrower}
            lender={lender}
            disabled={running}
            onBorrowerChange={setBorrower}
            onLenderChange={setLender}
            onLoadDemo={loadDemo}
            onSubmit={handleSubmit}
          />
          <LiveFeed events={events} running={running} />
        </div>

        <aside className="lg:sticky lg:top-6 lg:self-start">
          <ResultPanel result={result} error={error} />
        </aside>
      </main>
    </div>
  );
}
