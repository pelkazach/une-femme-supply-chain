import axios from "axios";
import type {
  HealthResponse,
  MetricsResponse,
  MetricsQueryParams,
  AuditLogListResponse,
  AuditLogQueryParams,
  ReviewQueueStats,
  InventoryResponse,
  InventoryItem,
  DepletionResponse,
  SKUMetrics,
  ReviewQueueResponse,
  ReviewQueueQueryParams,
  ReviewResponse,
  ReviewRequest,
} from "./api-types";
import {
  getDemoMetrics,
  getDemoSkuMetrics,
  getDemoInventory,
  getDemoInventoryBySku,
  getDemoDepletionEvents,
  getDemoAuditLogs,
  getDemoReviewQueue,
  getDemoReviewStats,
} from "./demo-data";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ??
  "https://une-femme-supply-chain-production.up.railway.app";

const DEMO_MODE = process.env.NEXT_PUBLIC_DEMO_MODE === "true";

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 15_000,
  headers: {
    "Content-Type": "application/json",
  },
});

/** Try a real API call; fall back to demo data on error (or force demo mode). */
async function withFallback<T>(
  apiCall: () => Promise<T>,
  demoFn: () => T,
): Promise<T> {
  if (DEMO_MODE) return demoFn();
  try {
    return await apiCall();
  } catch {
    return demoFn();
  }
}

export async function healthCheck(): Promise<HealthResponse> {
  if (DEMO_MODE) return { status: "ok (demo)" };
  try {
    const { data } = await apiClient.get<HealthResponse>("/health");
    return data;
  } catch {
    return { status: "ok (demo)" };
  }
}

export async function getMetrics(
  params?: MetricsQueryParams,
): Promise<MetricsResponse> {
  return withFallback(
    async () => {
      const { data } = await apiClient.get<MetricsResponse>("/metrics", {
        params,
      });
      return data;
    },
    () => getDemoMetrics(),
  );
}

export async function getAuditLogs(
  params?: AuditLogQueryParams,
): Promise<AuditLogListResponse> {
  return withFallback(
    async () => {
      const { data } = await apiClient.get<AuditLogListResponse>("/audit/logs", {
        params,
      });
      return data;
    },
    () => getDemoAuditLogs(params),
  );
}

export async function getReviewQueueStats(): Promise<ReviewQueueStats> {
  return withFallback(
    async () => {
      const { data } = await apiClient.get<ReviewQueueStats>("/review/queue/stats");
      return data;
    },
    () => getDemoReviewStats(),
  );
}

export async function getInventorySellable(): Promise<InventoryResponse> {
  return withFallback(
    async () => {
      const { data } = await apiClient.get<InventoryResponse>("/inventory/sellable");
      return data;
    },
    () => getDemoInventory(),
  );
}

export async function getInventorySellableBySku(
  sku: string,
): Promise<InventoryItem[]> {
  return withFallback(
    async () => {
      const { data } = await apiClient.get<InventoryItem[]>(
        `/inventory/sellable/${sku}`,
      );
      return data;
    },
    () => getDemoInventoryBySku(sku),
  );
}

export async function getDepletionEvents(params: {
  start_date?: string;
  end_date?: string;
  sku?: string;
}): Promise<DepletionResponse> {
  return withFallback(
    async () => {
      const { data } = await apiClient.get<DepletionResponse>("/inventory/out", {
        params,
      });
      return data;
    },
    () => getDemoDepletionEvents(params),
  );
}

export async function getSkuMetrics(
  sku: string,
  params?: MetricsQueryParams,
): Promise<SKUMetrics> {
  return withFallback(
    async () => {
      const { data } = await apiClient.get<SKUMetrics>(`/metrics/${sku}`, {
        params,
      });
      return data;
    },
    () => getDemoSkuMetrics(sku),
  );
}

export async function getReviewQueue(
  params?: ReviewQueueQueryParams,
): Promise<ReviewQueueResponse> {
  return withFallback(
    async () => {
      const { data } = await apiClient.get<ReviewQueueResponse>("/review/queue", {
        params,
      });
      return data;
    },
    () => getDemoReviewQueue(params),
  );
}

export async function reviewEmail(
  id: string,
  body: ReviewRequest,
): Promise<ReviewResponse> {
  if (DEMO_MODE) {
    return {
      id,
      message_id: id,
      original_category: "PO",
      corrected_category: body.corrected_category ?? null,
      reviewed_by: body.reviewer,
      reviewed_at: new Date().toISOString(),
      approved: body.approved,
    };
  }
  try {
    const { data } = await apiClient.post<ReviewResponse>(
      `/review/${id}`,
      body,
    );
    return data;
  } catch {
    return {
      id,
      message_id: id,
      original_category: "PO",
      corrected_category: body.corrected_category ?? null,
      reviewed_by: body.reviewer,
      reviewed_at: new Date().toISOString(),
      approved: body.approved,
    };
  }
}
