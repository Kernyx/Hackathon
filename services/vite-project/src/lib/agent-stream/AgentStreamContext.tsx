import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import type { NodeObject } from "react-force-graph-2d";
import { isWebhookPayload, type WebhookPayload } from "./types";

export type AgentRecord = {
  id: string;
  username: string;
  mood?: string;
  lastSeen?: string;
};

export interface AgentNode extends NodeObject {
  id: string;
  name: string;
  avatarSeed?: string;
  mood?: string;
  img?: HTMLImageElement;
  val?: number;
}

export type AgentLink = {
  source: string | AgentNode;
  target: string | AgentNode;
  message?: string;
  timestamp?: string;
};

export type GraphData = {
  nodes: AgentNode[];
  links: AgentLink[];
};

type Pulse = { sourceId: string; targetId: string; message?: string } | null;

type AgentStreamState = {
  isConnected: boolean;
  agents: AgentRecord[];
  agentsById: Map<string, AgentRecord>;
  graph: GraphData;
  selectedAgentId: string | null;
  hoveredAgentId: string | null;
  lastPulse: Pulse;
  rawEvents: Array<{ id: string; timestamp: string; payload: unknown }>;
};

type AgentStreamApi = AgentStreamState & {
  setSelectedAgentId: (id: string | null) => void;
  setHoveredAgentId: (id: string | null) => void;
  connect: (url?: string) => void;
  disconnect: () => void;
  sendJson: (payload: unknown) => boolean;
};

const AgentStreamContext = createContext<AgentStreamApi | null>(null);

const DEFAULT_WS_URL = "ws://localhost:8083/api/v1/audit/ws";

// module-scoped dedupe (survives StrictMode remounts)
const recentFingerprints = new Map<string, number>();
const shouldIgnoreAsDuplicate = (fingerprint: string, windowMs = 5000) => {
  const now = Date.now();
  const last = recentFingerprints.get(fingerprint);
  if (last && now - last < windowMs) return true;
  recentFingerprints.set(fingerprint, now);
  if (recentFingerprints.size > 800) {
    const entries = Array.from(recentFingerprints.entries()).sort((a, b) => a[1] - b[1]);
    for (let i = 0; i < 320; i++) recentFingerprints.delete(entries[i][0]);
  }
  return false;
};

const stableStringify = (value: unknown): string => {
  const seen = new WeakSet<object>();
  const normalize = (v: unknown): unknown => {
    if (!v || typeof v !== "object") return v;
    if (seen.has(v as object)) return "[Circular]";
    seen.add(v as object);
    if (Array.isArray(v)) return v.map(normalize);
    const obj = v as Record<string, unknown>;
    const keys = Object.keys(obj).sort();
    const out: Record<string, unknown> = {};
    for (const k of keys) out[k] = normalize(obj[k]);
    return out;
  };
  try {
    return JSON.stringify(normalize(value));
  } catch {
    return String(value);
  }
};

const fingerprintForWebhook = (p: WebhookPayload) => {
  const msg = p.data?.message ?? "";
  // timestamp can be re-sent; keep it in fp only if present
  return `wh:${p.event_type}:${p.source_agent.id}:${p.target_agents.map((t) => t.id).join(",")}:${p.timestamp}:${msg}`;
};

const fingerprintForAny = (payload: unknown) => `raw:${stableStringify(payload)}`;

export function AgentStreamProvider({ children }: { children: React.ReactNode }) {
  const wsRef = useRef<WebSocket | null>(null);
  const [isConnected, setIsConnected] = useState(false);

  // mutable maps keep stable object references for ForceGraph
  const agentsByIdRef = useRef<Map<string, AgentRecord>>(new Map());
  const nodesByIdRef = useRef<Map<string, AgentNode>>(new Map());
  const linksByKeyRef = useRef<Map<string, AgentLink>>(new Map());

  const [graph, setGraph] = useState<GraphData>({ nodes: [], links: [] });
  const [agents, setAgents] = useState<AgentRecord[]>([]);
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);
  const [hoveredAgentId, setHoveredAgentId] = useState<string | null>(null);
  const [lastPulse, setLastPulse] = useState<Pulse>(null);
  const [rawEvents, setRawEvents] = useState<AgentStreamState["rawEvents"]>([]);

  const upsertAgent = useCallback((id: string, username: string, mood: string | undefined, lastSeen: string) => {
    const existing = agentsByIdRef.current.get(id);
    if (existing) {
      existing.username = username || existing.username;
      existing.mood = mood ?? existing.mood;
      existing.lastSeen = lastSeen;
      return existing;
    }
    const next: AgentRecord = { id, username, mood, lastSeen };
    agentsByIdRef.current.set(id, next);
    return next;
  }, []);

  const upsertNode = useCallback((agent: AgentRecord) => {
    const existing = nodesByIdRef.current.get(agent.id);
    if (existing) {
      existing.name = agent.username || existing.name;
      existing.avatarSeed = agent.username || existing.avatarSeed;
      existing.mood = agent.mood ?? existing.mood;
      existing.val = 1;
      return existing;
    }
    const node: AgentNode = {
      id: agent.id,
      name: agent.username || "Unknown",
      avatarSeed: agent.username || agent.id,
      mood: agent.mood,
      val: 1,
    };
    nodesByIdRef.current.set(agent.id, node);
    return node;
  }, []);

  const upsertLink = useCallback((sourceId: string, targetId: string, message?: string, timestamp?: string) => {
    const key = `${sourceId}->${targetId}`;
    const existing = linksByKeyRef.current.get(key);
    if (existing) {
      existing.message = message ?? existing.message;
      existing.timestamp = timestamp ?? existing.timestamp;
      return existing;
    }
    const link: AgentLink = { source: sourceId, target: targetId, message: message ?? "", timestamp };
    linksByKeyRef.current.set(key, link);
    return link;
  }, []);

  const publishDerivedState = useCallback(() => {
    setAgents(Array.from(agentsByIdRef.current.values()));
    setGraph({
      nodes: Array.from(nodesByIdRef.current.values()),
      links: Array.from(linksByKeyRef.current.values()),
    });
  }, []);

  const ingestWebhookPayload = useCallback(
    (payload: WebhookPayload) => {
      const fp = fingerprintForWebhook(payload);
      if (shouldIgnoreAsDuplicate(fp, 5000)) return;

      const lastSeen = payload.timestamp || new Date().toISOString();
      const sourceMood = payload.data?.mood;
      const source = upsertAgent(payload.source_agent.id, payload.source_agent.username, sourceMood, lastSeen);
      upsertNode(source);

      const message = payload.data?.message;
      for (const t of payload.target_agents) {
        const target = upsertAgent(t.id, t.username, undefined, lastSeen);
        upsertNode(target);
        upsertLink(source.id, target.id, message, payload.timestamp);
        setLastPulse({ sourceId: source.id, targetId: target.id, message });
      }

      publishDerivedState();
    },
    [publishDerivedState, upsertAgent, upsertLink, upsertNode]
  );

  const ingestRawEvent = useCallback(
    (payload: unknown) => {
      const fp = fingerprintForAny(payload);
      if (shouldIgnoreAsDuplicate(fp, 1500)) return;

      setRawEvents((prev) => {
        const next = [
          ...prev,
          { id: crypto.randomUUID(), timestamp: new Date().toLocaleTimeString(), payload },
        ];
        // cap
        if (next.length > 600) return next.slice(next.length - 600);
        return next;
      });

      if (isWebhookPayload(payload)) ingestWebhookPayload(payload);
    },
    [ingestWebhookPayload]
  );

  const connect = useCallback((url?: string) => {
    const wsUrl = url || (import.meta as any).env?.VITE_AUDIT_WS_URL || DEFAULT_WS_URL;
    if (wsRef.current) return;

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => setIsConnected(true);
    ws.onerror = () => setIsConnected(false);
    ws.onclose = () => {
      setIsConnected(false);
      wsRef.current = null;
    };
    ws.onmessage = (event) => {
      try {
        const maybeJson = (() => {
          try {
            return JSON.parse(event.data);
          } catch {
            return event.data;
          }
        })();
        ingestRawEvent(maybeJson);
      } catch {
        // ignore
      }
    };
  }, [ingestRawEvent]);

  const disconnect = useCallback(() => {
    const ws = wsRef.current;
    wsRef.current = null;
    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
      ws.close();
    }
    setIsConnected(false);
  }, []);

  useEffect(() => {
    connect();
    return () => disconnect();
  }, [connect, disconnect]);

  const sendJson = useCallback((payload: unknown) => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return false;
    ws.send(typeof payload === "string" ? payload : JSON.stringify(payload));
    return true;
  }, []);

  const value: AgentStreamApi = useMemo(
    () => ({
      isConnected,
      agents,
      agentsById: agentsByIdRef.current,
      graph,
      selectedAgentId,
      hoveredAgentId,
      lastPulse,
      rawEvents,
      setSelectedAgentId,
      setHoveredAgentId,
      connect,
      disconnect,
      sendJson,
    }),
    [agents, connect, disconnect, graph, hoveredAgentId, isConnected, lastPulse, rawEvents, selectedAgentId, sendJson]
  );

  return <AgentStreamContext.Provider value={value}>{children}</AgentStreamContext.Provider>;
}

export const useAgentStream = () => {
  const ctx = useContext(AgentStreamContext);
  if (!ctx) throw new Error("useAgentStream must be used within AgentStreamProvider");
  return ctx;
};

