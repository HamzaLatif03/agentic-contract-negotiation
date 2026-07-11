import type { BorrowerTerms, DealTerms, LenderTerms, NegotiateRequest, StreamMessage } from "./types";

function clampPreference(value: number): number {
  return Math.max(1, Math.min(10, Math.round(value)));
}

function normalizeBorrower(raw: Partial<BorrowerTerms> & Record<string, unknown>): BorrowerTerms {
  const defaults = defaultBorrowerTerms();
  return {
    min_downpayment: Number(raw.min_downpayment ?? defaults.min_downpayment),
    max_downpayment: Number(raw.max_downpayment ?? defaults.max_downpayment),
    min_interest_rate_pct: Number(raw.min_interest_rate_pct ?? defaults.min_interest_rate_pct),
    max_interest_rate_pct: Number(raw.max_interest_rate_pct ?? defaults.max_interest_rate_pct),
    min_loan_length_years: Number(raw.min_loan_length_years ?? defaults.min_loan_length_years),
    max_loan_length_years: Number(raw.max_loan_length_years ?? defaults.max_loan_length_years),
    fixed_preference: clampPreference(
      Number(raw.fixed_preference ?? raw.min_interest_structure ?? defaults.fixed_preference),
    ),
    variable_preference: clampPreference(
      Number(raw.variable_preference ?? raw.max_interest_structure ?? defaults.variable_preference),
    ),
  };
}

function normalizeLender(raw: Partial<LenderTerms> & Record<string, unknown>): LenderTerms {
  const defaults = defaultLenderTerms();
  return {
    min_downpayment: Number(raw.min_downpayment ?? defaults.min_downpayment),
    max_downpayment: Number(raw.max_downpayment ?? defaults.max_downpayment),
    min_interest_rate_pct: Number(raw.min_interest_rate_pct ?? defaults.min_interest_rate_pct),
    max_interest_rate_pct: Number(raw.max_interest_rate_pct ?? defaults.max_interest_rate_pct),
    min_loan_length_years: Number(raw.min_loan_length_years ?? defaults.min_loan_length_years),
    max_loan_length_years: Number(raw.max_loan_length_years ?? defaults.max_loan_length_years),
    fixed_preference: clampPreference(
      Number(raw.fixed_preference ?? raw.min_interest_structure ?? defaults.fixed_preference),
    ),
    variable_preference: clampPreference(
      Number(raw.variable_preference ?? raw.max_interest_structure ?? defaults.variable_preference),
    ),
  };
}

export function demoTerms(): NegotiateRequest {
  return {
    borrower: defaultBorrowerTerms(),
    lender: defaultLenderTerms(),
  };
}

export async function fetchDemoTerms(): Promise<NegotiateRequest> {
  try {
    const response = await fetch("/api/demo");
    if (!response.ok) {
      return demoTerms();
    }
    const data = (await response.json()) as {
      borrower?: Partial<BorrowerTerms> & Record<string, unknown>;
      lender?: Partial<LenderTerms> & Record<string, unknown>;
    };
    return {
      borrower: normalizeBorrower(data.borrower ?? {}),
      lender: normalizeLender(data.lender ?? {}),
    };
  } catch {
    return demoTerms();
  }
}

export async function checkHealth(): Promise<boolean> {
  try {
    const response = await fetch("/api/health");
    return response.ok;
  } catch {
    return false;
  }
}

export async function fetchModels(): Promise<{
  default: string;
  catalog: Array<{
    id: string;
    label: string;
    ollama_name?: string;
    description: string;
    available: boolean;
    resolved_name: string;
    runtime?: "api" | "ollama";
  }>;
  installed: string[];
}> {
  const response = await fetch("/api/models");
  if (!response.ok) {
    let detail = `Could not list models (${response.status})`;
    try {
      const payload = (await response.json()) as { detail?: string };
      if (payload.detail) detail = payload.detail;
    } catch {
      // ignore
    }
    throw new Error(detail);
  }
  const data = (await response.json()) as {
    default?: string;
    catalog?: Array<{
      id: string;
      label: string;
      ollama_name?: string;
      description: string;
      available: boolean;
      resolved_name: string;
      runtime?: "api" | "ollama";
    }>;
    installed?: string[];
    models?: string[];
  };

  const catalog = Array.isArray(data.catalog) ? data.catalog : [];
  const installed = Array.isArray(data.installed)
    ? data.installed
    : Array.isArray(data.models)
      ? data.models
      : [];
  const defaultModel =
    data.default ||
    catalog.find((row) => row.available)?.resolved_name ||
    installed[0] ||
    "llama3.3:70b";

  return {
    default: defaultModel,
    catalog,
    installed,
  };
}

export async function parseOfferPdf(file: File): Promise<{
  opening_offer: DealTerms;
  source_filename: string | null;
}> {
  const body = new FormData();
  body.append("file", file);
  const response = await fetch("/api/parse-offer-pdf", {
    method: "POST",
    body,
  });
  if (!response.ok) {
    let detail = `Upload failed (${response.status})`;
    try {
      const payload = (await response.json()) as { detail?: string };
      if (payload.detail) detail = payload.detail;
    } catch {
      // ignore JSON parse errors
    }
    throw new Error(detail);
  }
  const data = (await response.json()) as {
    opening_offer: DealTerms;
    source_filename?: string | null;
  };
  return {
    opening_offer: {
      ...data.opening_offer,
      consensus_reached: false,
    },
    source_filename: data.source_filename ?? file.name,
  };
}

export function streamNegotiation(
  request: NegotiateRequest,
  onMessage: (message: StreamMessage) => void,
  onError: (error: Error) => void,
  onComplete: () => void,
): () => void {
  const controller = new AbortController();

  (async () => {
    try {
      const response = await fetch("/api/negotiate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(request),
        signal: controller.signal,
      });

      if (!response.ok) {
        throw new Error(`Request failed (${response.status})`);
      }

      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error("No response stream");
      }

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const payload = JSON.parse(line.slice(6)) as StreamMessage;
          onMessage(payload);
          if (payload.type === "complete" || payload.type === "error") {
            onComplete();
            return;
          }
        }
      }

      onComplete();
    } catch (error) {
      if (controller.signal.aborted) return;
      onError(error instanceof Error ? error : new Error(String(error)));
      onComplete();
    }
  })();

  return () => controller.abort();
}

export const defaultBorrowerTerms = (): BorrowerTerms => ({
  min_downpayment: 60_000,
  max_downpayment: 80_000,
  min_interest_rate_pct: 4.0,
  max_interest_rate_pct: 5.5,
  min_loan_length_years: 20,
  max_loan_length_years: 25,
  fixed_preference: 8,
  variable_preference: 3,
});

export const defaultLenderTerms = (): LenderTerms => ({
  min_downpayment: 50_000,
  max_downpayment: 100_000,
  min_interest_rate_pct: 4.5,
  max_interest_rate_pct: 6.0,
  min_loan_length_years: 10,
  max_loan_length_years: 30,
  fixed_preference: 2,
  variable_preference: 9,
});
