import { apiBaseUrl } from "../config/environment";

export interface HealthResponse {
  service: string;
  status: string;
  version: string;
}

export async function fetchGatewayHealth(): Promise<HealthResponse> {
  const response = await fetch(`${apiBaseUrl}/health`);
  if (!response.ok) throw new Error("Gateway health request failed");
  return response.json() as Promise<HealthResponse>;
}
