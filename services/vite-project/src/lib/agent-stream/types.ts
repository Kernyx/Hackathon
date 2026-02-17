export type AgentIdentity = {
  id: string;
  username: string;
};

export type WebhookPayload = {
  event_type: string;
  source_agent: AgentIdentity;
  target_agents: AgentIdentity[];
  timestamp: string; // ISO
  data?: {
    message?: string;
    mood?: string;
    [key: string]: unknown;
  };
};

export const isWebhookPayload = (value: unknown): value is WebhookPayload => {
  if (!value || typeof value !== "object") return false;
  const v = value as any;
  if (typeof v.event_type !== "string") return false;
  if (!v.source_agent || typeof v.source_agent !== "object") return false;
  if (typeof v.source_agent.id !== "string") return false;
  if (typeof v.source_agent.username !== "string") return false;
  if (!Array.isArray(v.target_agents)) return false;
  if (typeof v.timestamp !== "string") return false;
  // target_agents entries validation (best-effort)
  for (const t of v.target_agents) {
    if (!t || typeof t !== "object") return false;
    if (typeof (t as any).id !== "string") return false;
    if (typeof (t as any).username !== "string") return false;
  }
  return true;
};

