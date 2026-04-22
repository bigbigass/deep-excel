export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

type KpiCard = {
  label: string;
  value: string;
};

type TemplateDecision = {
  template_id: string;
  reason: string;
};

type ChartSpec = {
  chart_id: string;
  chart_type: string;
  title: string;
};

type AnomalyItem = {
  type?: string;
  severity?: string;
  summary?: string;
};

type NarrativeBlock = {
  executive_summary: string;
  quality_risk: string;
  recommended_actions: string[];
};

export type JobTaskStatus = "pending" | "running" | "completed" | "failed";

export type JobTaskItem = {
  id: string;
  label: string;
  status: JobTaskStatus;
  error: string | null;
};

export type JobPayload = {
  job_id: string;
  state: "queued" | "running" | "analysis_completed" | "rendering" | "completed" | "failed";
  error: string | null;
  created_at: string;
  updated_at: string;
  source_file_name: string;
  tasks: JobTaskItem[];
  template_id: string | null;
  chart_paths: Record<string, string>;
  report_id: string | null;
  download_path: string | null;
  report_spec: {
    template_decision: TemplateDecision;
    dataset_summary: {
      sample_count?: number;
      overall_pass_rate?: number;
    };
    kpi_cards: KpiCard[];
    chart_specs: ChartSpec[];
    anomalies: AnomalyItem[];
    ai_narrative: NarrativeBlock;
  } | null;
};

export type UpstreamCheckPayload = {
  configured: boolean;
  reachable: boolean;
  model: string;
  base_url: string | null;
  latency_ms: number | null;
  response_preview: string | null;
  error: string | null;
};

export type UploadProgressCallback = (progress: number) => void;

async function parseJsonResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    throw new Error(`Request failed with status ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export async function createJob(
  file: File,
  onUploadProgress?: UploadProgressCallback
): Promise<{ job_id: string }> {
  const formData = new FormData();
  formData.append("file", file);

  if (!onUploadProgress || typeof XMLHttpRequest === "undefined") {
    const response = await fetch(`${API_BASE_URL}/api/v1/jobs`, { method: "POST", body: formData });
    return parseJsonResponse<{ job_id: string }>(response);
  }

  onUploadProgress(0);

  return new Promise<{ job_id: string }>((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("POST", `${API_BASE_URL}/api/v1/jobs`);
    request.responseType = "json";

    request.upload.addEventListener("progress", (event) => {
      const total = event.lengthComputable ? event.total : file.size;
      const percent = total > 0 ? Math.min(100, Math.round((event.loaded / total) * 100)) : 0;
      onUploadProgress(percent);
    });

    request.addEventListener("load", () => {
      if (request.status < 200 || request.status >= 300) {
        reject(new Error(`Request failed with status ${request.status}`));
        return;
      }

      onUploadProgress(100);

      if (request.response && typeof request.response === "object") {
        resolve(request.response as { job_id: string });
        return;
      }

      try {
        resolve(JSON.parse(request.responseText) as { job_id: string });
      } catch {
        reject(new Error("Invalid JSON response from create job endpoint"));
      }
    });

    request.addEventListener("error", () => reject(new Error("Create job request failed")));
    request.addEventListener("abort", () => reject(new Error("Create job request aborted")));
    request.send(formData);
  });
}

export async function getJob(jobId: string): Promise<JobPayload> {
  const response = await fetch(`${API_BASE_URL}/api/v1/jobs/${jobId}`, { cache: "no-store" });
  return parseJsonResponse<JobPayload>(response);
}

export async function renderJob(jobId: string): Promise<{ job_id: string }> {
  const response = await fetch(`${API_BASE_URL}/api/v1/jobs/${jobId}/render`, { method: "POST" });
  return parseJsonResponse<{ job_id: string }>(response);
}

export async function checkUpstreamHealth(): Promise<UpstreamCheckPayload> {
  const response = await fetch(`${API_BASE_URL}/api/v1/health/upstream-check`, {
    method: "POST",
    cache: "no-store"
  });
  if (!response.ok) {
    throw new Error(`Upstream check failed with status ${response.status}`);
  }
  return response.json();
}
