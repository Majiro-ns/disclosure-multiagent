import type {
  CompanyInfo,
  EdinetDocument,
  PipelineStatus,
  StepStartResponse,
  StepNextResponse,
} from '@/types';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API error ${res.status}: ${text}`);
  }
  return res.json();
}

// ── EDINET / Company Search ──────────────────────────────

export async function searchCompany(params: {
  sec_code?: string;
  edinet_code?: string;
  name?: string;
}): Promise<{ results: CompanyInfo[]; total: number }> {
  const qs = new URLSearchParams();
  if (params.sec_code) qs.set('sec_code', params.sec_code);
  if (params.edinet_code) qs.set('edinet_code', params.edinet_code);
  if (params.name) qs.set('name', params.name);
  return fetchJson(`/api/edinet/search?${qs}`);
}

export async function getEdinetDocuments(
  date: string,
  docType = '120'
): Promise<{ documents: EdinetDocument[]; total: number }> {
  return fetchJson(`/api/edinet/documents?date=${date}&doc_type=${docType}`);
}

// ── Analysis ─────────────────────────────────────────────

export async function startAnalysis(params: {
  edinet_code?: string;
  sec_code?: string;
  company_name?: string;
  fiscal_year?: number;
  fiscal_month_end?: number;
  level?: string;
  pdf_doc_id?: string;
  use_mock?: boolean;
}): Promise<{ task_id: string; status: string; message: string }> {
  return fetchJson('/api/analyze', {
    method: 'POST',
    body: JSON.stringify({
      edinet_code: params.edinet_code,
      sec_code: params.sec_code,
      company_name: params.company_name || '',
      fiscal_year: params.fiscal_year || 2025,
      fiscal_month_end: params.fiscal_month_end || 3,
      level: params.level || '竹',
      pdf_doc_id: params.pdf_doc_id,
      use_mock: params.use_mock ?? true,
    }),
  });
}

export async function uploadPdfAnalysis(params: {
  file: File;
  company_name?: string;
  fiscal_year?: number;
  fiscal_month_end?: number;
  level?: string;
  use_mock?: boolean;
  use_debug?: boolean;
}): Promise<{ task_id: string; status: string; message: string }> {
  const form = new FormData();
  form.append('file', params.file);
  form.append('company_name', params.company_name ?? '');
  form.append('fiscal_year', String(params.fiscal_year ?? 2025));
  form.append('fiscal_month_end', String(params.fiscal_month_end ?? 3));
  form.append('level', params.level ?? '竹');
  form.append('use_mock', String(params.use_mock ?? true));
  form.append('use_debug', String(params.use_debug ?? false));

  const res = await fetch(`${API_BASE}/api/analyze/upload`, {
    method: 'POST',
    body: form,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API error ${res.status}: ${text}`);
  }
  return res.json();
}

export async function getTaskStatus(taskId: string): Promise<PipelineStatus> {
  return fetchJson(`/api/status/${taskId}`);
}

// ── SSE Stream ───────────────────────────────────────────

// ── Step Execution API ────────────────────────────────────

export async function startStepExecution(params: {
  file: File;
  company_name?: string;
  fiscal_year?: number;
  fiscal_month_end?: number;
  level?: string;
  use_mock?: boolean;
  use_debug?: boolean;
}): Promise<StepStartResponse> {
  const form = new FormData();
  form.append('file', params.file);
  form.append('company_name', params.company_name ?? '');
  form.append('fiscal_year', String(params.fiscal_year ?? 2025));
  form.append('fiscal_month_end', String(params.fiscal_month_end ?? 3));
  form.append('level', params.level ?? '竹');
  form.append('use_mock', String(params.use_mock ?? true));
  form.append('use_debug', String(params.use_debug ?? false));

  const res = await fetch(`${API_BASE}/api/step/start`, {
    method: 'POST',
    body: form,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API error ${res.status}: ${text}`);
  }
  return res.json();
}

export async function executeNextStep(taskId: string): Promise<StepNextResponse> {
  return fetchJson(`/api/step/${taskId}/next`, { method: 'POST' });
}

export async function getStepOutput(taskId: string, stage: string): Promise<StepNextResponse> {
  return fetchJson(`/api/step/${taskId}/output/${stage}`);
}

export async function runAllRemaining(taskId: string): Promise<{ status: string; task_id: string }> {
  return fetchJson(`/api/step/${taskId}/run-all`, { method: 'POST' });
}

// ── SSE Stream ───────────────────────────────────────────

export function streamTaskStatus(
  taskId: string,
  onUpdate: (status: PipelineStatus) => void,
  onComplete: (status: PipelineStatus) => void,
  onError?: (error: Error) => void
): () => void {
  const eventSource = new EventSource(`${API_BASE}/api/status/${taskId}/stream`);

  eventSource.addEventListener('status', (event) => {
    try {
      const data = JSON.parse(event.data) as PipelineStatus;
      onUpdate(data);
    } catch (e) {
      onError?.(e as Error);
    }
  });

  eventSource.addEventListener('complete', (event) => {
    try {
      const data = JSON.parse(event.data) as PipelineStatus;
      onComplete(data);
    } catch (e) {
      onError?.(e as Error);
    }
    eventSource.close();
  });

  eventSource.onerror = () => {
    onError?.(new Error('SSE connection error'));
    eventSource.close();
  };

  return () => eventSource.close();
}
