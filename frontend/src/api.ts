import type {
  DealTerms,
  InitialPeriodYears,
  NegotiateRequest,
  PartyTerms,
  PersonaSummary,
  RateType,
  RepaymentType,
  StreamMessage,
} from "./types";

function num(value: unknown, fallback: number): number {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
}

function featurePref(value: unknown, fallback: number): number {
  if (typeof value === "boolean") return value ? 8 : 3;
  const text = String(value ?? "").toLowerCase();
  if (["true", "yes", "y", "on"].includes(text)) return 8;
  if (["false", "no", "n", "off"].includes(text)) return 3;
  const n = Number(value);
  if (!Number.isFinite(n)) return fallback;
  return Math.max(1, Math.min(10, Math.round(n)));
}

function rateType(value: unknown, fallback: RateType): RateType {
  const text = String(value ?? fallback).toLowerCase();
  if (text === "fixed" || text === "tracker" || text === "discount") return text;
  const n = Number(value);
  if (Number.isFinite(n)) {
    if (n <= 4) return "fixed";
    if (n <= 7) return "discount";
    return "tracker";
  }
  return fallback;
}

function period(value: unknown, fallback: InitialPeriodYears): InitialPeriodYears {
  const n = Number(value);
  if (n === 2 || n === 5 || n === 10) return n;
  return fallback;
}

function repayment(value: unknown, fallback: RepaymentType): RepaymentType {
  const text = String(value ?? fallback).toLowerCase().replaceAll("-", "_");
  if (text === "interest_only") return "interest_only";
  return "capital_repayment";
}

function normalizeParty(
  raw: Partial<PartyTerms> & Record<string, unknown>,
  defaults: PartyTerms,
): PartyTerms {
  return {
    min_downpayment: num(raw.min_downpayment, defaults.min_downpayment),
    max_downpayment: num(raw.max_downpayment, defaults.max_downpayment),
    min_interest_rate_pct: num(raw.min_interest_rate_pct, defaults.min_interest_rate_pct),
    max_interest_rate_pct: num(raw.max_interest_rate_pct, defaults.max_interest_rate_pct),
    min_loan_length_years: num(raw.min_loan_length_years, defaults.min_loan_length_years),
    max_loan_length_years: num(raw.max_loan_length_years, defaults.max_loan_length_years),
    min_arrangement_fee: num(raw.min_arrangement_fee, defaults.min_arrangement_fee),
    max_arrangement_fee: num(raw.max_arrangement_fee, defaults.max_arrangement_fee),
    min_cashback: num(raw.min_cashback, defaults.min_cashback),
    max_cashback: num(raw.max_cashback, defaults.max_cashback),
    min_overpayment_allowance_pct: num(
      raw.min_overpayment_allowance_pct,
      defaults.min_overpayment_allowance_pct,
    ),
    max_overpayment_allowance_pct: num(
      raw.max_overpayment_allowance_pct,
      defaults.max_overpayment_allowance_pct,
    ),
    min_erc_pct: num(raw.min_erc_pct, defaults.min_erc_pct),
    max_erc_pct: num(raw.max_erc_pct, defaults.max_erc_pct),
    preferred_rate_type: rateType(raw.preferred_rate_type, defaults.preferred_rate_type),
    preferred_initial_period_years: period(
      raw.preferred_initial_period_years,
      defaults.preferred_initial_period_years,
    ),
    preferred_repayment_type: repayment(
      raw.preferred_repayment_type,
      defaults.preferred_repayment_type,
    ),
    portable_preference: featurePref(
      raw.portable_preference ?? raw.prefer_portable,
      defaults.portable_preference,
    ),
    free_valuation_preference: featurePref(
      raw.free_valuation_preference ?? raw.prefer_free_valuation,
      defaults.free_valuation_preference,
    ),
    free_legal_preference: featurePref(
      raw.free_legal_preference ?? raw.prefer_free_legal,
      defaults.free_legal_preference,
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
  return fetchPersonaTerms("demo");
}

export async function fetchPersonas(): Promise<PersonaSummary[]> {
  try {
    const response = await fetch("/api/personas");
    if (!response.ok) return [];
    const data = (await response.json()) as { personas?: PersonaSummary[] };
    return data.personas ?? [];
  } catch {
    return [];
  }
}

export async function fetchPersonaTerms(personaId: string): Promise<NegotiateRequest> {
  try {
    const response = await fetch(`/api/personas/${encodeURIComponent(personaId)}`);
    if (!response.ok) {
      return demoTerms();
    }
    const data = (await response.json()) as {
      borrower?: Partial<PartyTerms> & Record<string, unknown>;
      lender?: Partial<PartyTerms> & Record<string, unknown>;
    };
    return {
      borrower: normalizeParty(data.borrower ?? {}, defaultBorrowerTerms()),
      lender: normalizeParty(data.lender ?? {}, defaultLenderTerms()),
    };
  } catch {
    return demoTerms();
  }
}

export async function previewOpeningOffer(pdfFile: File): Promise<{
  model: string;
  filename: string | null;
  announcement: string;
  deal: DealTerms;
}> {
  const form = new FormData();
  form.append("file", pdfFile);
  const response = await fetch("/api/preview-opening-offer", {
    method: "POST",
    body: form,
  });
  if (!response.ok) {
    let detail = `Preview failed (${response.status})`;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  const data = (await response.json()) as {
    model: string;
    filename?: string | null;
    announcement: string;
    deal: DealTerms;
  };
  return {
    model: data.model,
    filename: data.filename ?? pdfFile.name,
    announcement: data.announcement,
    deal: data.deal,
  };
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

  return {
    default: data.default ?? "gemini-3.1-flash-lite",
    catalog: data.catalog ?? [],
    installed: data.installed ?? data.models ?? [],
  };
}

export function streamNegotiation(
  request: NegotiateRequest,
  options: {
    onMessage: (msg: StreamMessage) => void;
    onError: (error: Error) => void;
    onComplete: () => void;
    pdfFile?: File | null;
  },
): () => void {
  const { onMessage, onError, onComplete, pdfFile } = options;
  const controller = new AbortController();

  void (async () => {
    try {
      let response: Response;
      if (pdfFile) {
        const form = new FormData();
        form.append("borrower", JSON.stringify(request.borrower));
        form.append("lender", JSON.stringify(request.lender));
        if (request.llm_model) form.append("llm_model", request.llm_model);
        if (request.persona_id) form.append("persona_id", request.persona_id);
        if (request.persona_name) form.append("persona_name", request.persona_name);
        if (request.attempt != null) form.append("attempt", String(request.attempt));
        form.append("file", pdfFile);
        response = await fetch("/api/negotiate-with-pdf", {
          method: "POST",
          body: form,
          signal: controller.signal,
        });
      } else {
        const {
          borrower,
          lender,
          llm_model,
          contract_text,
          persona_id,
          persona_name,
          attempt,
        } = request;
        response = await fetch("/api/negotiate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            borrower,
            lender,
            llm_model,
            contract_text,
            persona_id,
            persona_name,
            attempt,
          }),
          signal: controller.signal,
        });
      }

      if (!response.ok || !response.body) {
        throw new Error(`Negotiation failed (${response.status})`);
      }

      const reader = response.body.getReader();
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

export const defaultBorrowerTerms = (): PartyTerms => ({
  min_downpayment: 60_000,
  max_downpayment: 80_000,
  min_interest_rate_pct: 4.0,
  max_interest_rate_pct: 5.5,
  min_loan_length_years: 20,
  max_loan_length_years: 25,
  min_arrangement_fee: 0,
  max_arrangement_fee: 999,
  min_cashback: 500,
  max_cashback: 5_000,
  min_overpayment_allowance_pct: 10,
  max_overpayment_allowance_pct: 20,
  min_erc_pct: 0,
  max_erc_pct: 3,
  preferred_rate_type: "fixed",
  preferred_initial_period_years: 5,
  preferred_repayment_type: "capital_repayment",
  portable_preference: 8,
  free_valuation_preference: 7,
  free_legal_preference: 7,
});

export const defaultLenderTerms = (): PartyTerms => ({
  min_downpayment: 50_000,
  max_downpayment: 100_000,
  min_interest_rate_pct: 4.5,
  max_interest_rate_pct: 6.0,
  min_loan_length_years: 10,
  max_loan_length_years: 30,
  min_arrangement_fee: 0,
  max_arrangement_fee: 1_499,
  min_cashback: 0,
  max_cashback: 2_000,
  min_overpayment_allowance_pct: 5,
  max_overpayment_allowance_pct: 10,
  min_erc_pct: 1,
  max_erc_pct: 5,
  preferred_rate_type: "tracker",
  preferred_initial_period_years: 2,
  preferred_repayment_type: "capital_repayment",
  portable_preference: 3,
  free_valuation_preference: 3,
  free_legal_preference: 2,
});
