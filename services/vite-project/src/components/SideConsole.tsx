import React, { useEffect, useRef, useState } from "react"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { SendHorizontal, Terminal, User, WifiOff } from "lucide-react"
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command"
import { useAgentStream } from "@/lib/agent-stream/AgentStreamContext"

interface LogEvent {
  id: string;
  timestamp: string;
  data: any;
  type?: 'system' | 'error' | 'info';
}

/**
 * Dedupe cache is module-scoped on purpose.
 * In dev, React.StrictMode intentionally remounts components and `useRef` state resets.
 * If the WS reconnect causes the server to replay/broadcast the same payloads again,
 * we'd otherwise re-add them and the UI looks like it "duplicates" messages.
 */
const recentFingerprints = new Map<string, number>();

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

const fingerprintForEventData = (data: unknown): string => {
  if (typeof data === "string") return `str:${data}`;
  if (!data) return `nil:${String(data)}`;

  if (typeof data === "object") {
    const obj = data as any;
    const id = obj?.id ?? obj?.eventId ?? obj?.uuid ?? obj?.message_id;
    if (id != null) return `id:${String(id)}`;

    // remove the most common volatile fields so replays match
    const { timestamp, ts, createdAt, updatedAt, ...rest } = obj ?? {};
    return `obj:${stableStringify(rest)}`;
  }

  return `other:${String(data)}`;
};

const shouldIgnoreAsDuplicate = (fingerprint: string, windowMs = 5000) => {
  const now = Date.now();
  const last = recentFingerprints.get(fingerprint);
  if (last && now - last < windowMs) return true;

  recentFingerprints.set(fingerprint, now);

  // prevent unbounded growth
  if (recentFingerprints.size > 600) {
    const entries = Array.from(recentFingerprints.entries()).sort((a, b) => a[1] - b[1]);
    for (let i = 0; i < 240; i++) recentFingerprints.delete(entries[i][0]);
  }

  return false;
};

export function SideConsole() {
  const {
    isConnected,
    agents,
    agentsById,
    rawEvents,
    selectedAgentId,
    setSelectedAgentId,
    sendJson,
  } = useAgentStream();
  const [open, setOpen] = useState(false)
  const [events, setEvents] = useState<LogEvent[]>([])
  const [inputValue, setInputValue] = useState("")
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const selectedAgent = selectedAgentId ? agentsById.get(selectedAgentId) : null;

  // Функция для добавления системных логов (ошибки, коннекты)
  const addSystemLog = (message: string, type: 'system' | 'error' = 'system') => {
    const fingerprint = `system:${type}:${message}`;
    if (shouldIgnoreAsDuplicate(fingerprint, 3000)) return;
    
    const newMsg: LogEvent = {
      id: crypto.randomUUID(),
      timestamp: new Date().toLocaleTimeString(),
      data: message,
      type: type,
    };
    setEvents(prev => [...prev, newMsg]);
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [events]);

  // Mirror stream events into console UI (deduped)
  useEffect(() => {
    if (rawEvents.length === 0) return;
    const last = rawEvents[rawEvents.length - 1];
    const fingerprint = `msg:${fingerprintForEventData(last.payload)}`;
    if (shouldIgnoreAsDuplicate(fingerprint, 5000)) return;

    setEvents((prev) => [
      ...prev,
      {
        id: last.id,
        timestamp: last.timestamp,
        data: last.payload,
        type: "info",
      },
    ]);
  }, [rawEvents]);

  // connection status logs
  const prevConnRef = useRef<boolean | null>(null);
  useEffect(() => {
    if (prevConnRef.current === null) {
      prevConnRef.current = isConnected;
      return;
    }
    if (prevConnRef.current !== isConnected) {
      addSystemLog(isConnected ? "Connected to audit server" : "Disconnected from server", "system");
      prevConnRef.current = isConnected;
    }
  }, [isConnected]);

  const handleSendMessage = () => {
    if (!inputValue.trim() || !isConnected) return;

    const payload = {
      text: inputValue,
      target: selectedAgent ? selectedAgent.id : 'global',
      timestamp: new Date().toISOString()
    };

    sendJson(payload);
    setInputValue("");
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') handleSendMessage();
  }

  const filteredEvents = selectedAgent ? events : events;

  return (
    <>
      <aside className="fixed right-4 top-[10%] bottom-[10%] w-80 hidden xl:flex flex-col bg-card/80 backdrop-blur-md border border-border rounded-2xl shadow-2xl overflow-hidden z-40">
        
        {/* 1. ШАПКА */}
        <div className="h-14 flex items-center justify-between px-3 bg-muted/30 border-b border-border shrink-0">
          <div className="flex items-center gap-2">
            <Terminal className="h-4 w-4 text-primary" />
            <span className="text-[10px] font-bold uppercase tracking-widest opacity-70">
              {selectedAgent ? `Logs: ${selectedAgent.username}` : "Global Logs"}
            </span>
            <div className={`h-2 w-2 rounded-full transition-colors ${isConnected ? 'bg-green-500 shadow-[0_0_5px_#22c55e]' : 'bg-red-500'}`} />
          </div>

          <Button 
            variant="outline" 
            size="sm" 
            onClick={() => setOpen(true)}
            className="h-7 px-2 text-[11px] bg-background/50 border-muted gap-1.5"
          >
            <User className="h-3.5 w-3.5" />
            {selectedAgent ? selectedAgent.username : "All Agents"}
          </Button>
        </div>

        {/* 2. СЕКЦИЯ ЛОГОВ */}
        <div className="flex-1 min-h-0 relative"> 
          <ScrollArea className="h-full w-full"> 
            <div className="p-4 space-y-3 text-[11px] leading-relaxed">
              {filteredEvents.map((event) => (
                <div key={event.id} className={`animate-in fade-in slide-in-from-bottom-1 duration-300 border-l-2 pl-3 py-1.5 rounded-r transition-colors ${
                  event.type === 'error' ? 'border-red-500/50 bg-red-500/5' : 
                  event.type === 'system' ? 'border-yellow-500/50 bg-yellow-500/5' : 'border-primary/20 bg-muted/30'
                }`}>
                  <div className="flex items-baseline gap-2 mb-1">
                    <span className="text-primary/70 text-[10px] font-medium">[{event.timestamp}]</span>
                    {event.type === 'error' && <span className="text-red-400 font-bold uppercase text-[9px] tracking-wider">Error</span>}
                    {event.type === 'system' && <span className="text-yellow-400 font-bold uppercase text-[9px] tracking-wider">System</span>}
                  </div>
                  <div className={`break-all whitespace-pre-wrap text-[11px] ${
                    event.type === 'error' ? 'text-red-200' : 
                    event.type === 'system' ? 'text-yellow-100/90' : 'text-foreground/80'
                  }`}>
                    {typeof event.data === 'object' ? JSON.stringify(event.data, null, 2) : String(event.data)}
                  </div>
                </div>
              ))}
              <div ref={messagesEndRef} />
            </div>
          </ScrollArea>
        </div>

        <Separator />

        {/* 3. ЧАТ */}
        <div className="p-3 bg-muted/20 shrink-0 h-auto border-t border-border/50">
          <div className="mb-2 text-[11px] font-medium text-muted-foreground px-1 flex justify-between items-center">
            <span className="uppercase tracking-wider">{selectedAgent ? `Private: ${selectedAgent.username}` : "Global Broadcast"}</span>
            <span className={`text-[10px] font-semibold uppercase tracking-wider ${isConnected ? "text-green-500" : "text-red-500"}`}>
                {isConnected ? "ONLINE" : "OFFLINE"}
            </span>
          </div>
          <div className="relative flex items-center gap-2">
            <Input 
              disabled={!isConnected}
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={isConnected ? "Send message..." : "Waiting for connection..."} 
              className="pr-10 text-[11px] bg-background/50 border-muted focus-visible:ring-primary/30"
            />
            <Button 
                size="icon" 
                variant="ghost" 
                className="h-9 w-9 text-primary hover:bg-primary/10 shrink-0"
                onClick={handleSendMessage}
                disabled={!isConnected}
            >
              {isConnected ? <SendHorizontal className="h-4 w-4" /> : <WifiOff className="h-4 w-4 opacity-50"/>}
            </Button>
          </div>
        </div>
      </aside>

      <CommandDialog open={open} onOpenChange={setOpen}>
        {/* ... (остальной код модалки без изменений) ... */}
        <CommandInput placeholder="Type a name or 'all'..." />
        <CommandList>
          <CommandEmpty>No results found.</CommandEmpty>
          <CommandGroup heading="General">
            <CommandItem onSelect={() => { setSelectedAgentId(null); setOpen(false); }} className="cursor-pointer font-bold text-primary">
              <User className="mr-2 h-4 w-4" />
              <span>All Agents (Global Chat)</span>
            </CommandItem>
          </CommandGroup>
          <CommandGroup heading="Individual Agents">
            {agents.map((agent) => (
              <CommandItem
                key={agent.id}
                onSelect={() => { setSelectedAgentId(agent.id); setOpen(false); }}
                className="cursor-pointer"
              >
                <User className="mr-2 h-4 w-4 opacity-50" />
                <span>{agent.username}</span>
                <span className="ml-auto text-[10px] opacity-40">{agent.mood ?? ""}</span>
              </CommandItem>
            ))}
          </CommandGroup>
        </CommandList>
      </CommandDialog>
    </>
  )
}