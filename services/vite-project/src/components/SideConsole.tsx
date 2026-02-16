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

interface LogEvent {
  id: string;
  timestamp: string;
  data: any;
  type?: 'system' | 'error' | 'info';
}

export function SideConsole({ agents = [] }: { agents?: any[] }) {
  const [open, setOpen] = useState(false)
  const [selectedAgent, setSelectedAgent] = useState<any>(null)
  
  const [isConnected, setIsConnected] = useState(true)
  const [events, setEvents] = useState<LogEvent[]>([])
  const [inputValue, setInputValue] = useState("")
  
  const wsRef = useRef<WebSocket | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Функция для добавления системных логов (ошибки, коннекты)
  const addSystemLog = (message: string, type: 'system' | 'error' = 'system') => {
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

  useEffect(() => {
    if (wsRef.current) return;

    const ws = new WebSocket('ws://localhost:8083/api/v1/audit/ws');
    wsRef.current = ws;

    ws.onopen = () => {
      console.log('WebSocket Connected');
      setIsConnected(true);
      addSystemLog("Connected to audit server");
    };

    ws.onmessage = (event) => {
      try {
        let displayData;
        try {
          displayData = JSON.parse(event.data);
        } catch {
          displayData = event.data;
        }

        setEvents(prev => [
          ...prev,
          {
            id: crypto.randomUUID(),
            timestamp: new Date().toLocaleTimeString(),
            data: displayData,
            type: 'info'
          }
        ]);
      } catch (e) {
        console.error("Message error", e);
      }
    };

    ws.onerror = () => {
      addSystemLog("Connection error occurred", "error");
      setIsConnected(false);
    };

    ws.onclose = () => {
      addSystemLog("Disconnected from server", "system");
      setIsConnected(false);
      wsRef.current = null;
    };

    return () => {
      if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
        ws.close();
      }
      wsRef.current = null;
    };
  }, []);

  const handleSendMessage = () => {
    if (!inputValue.trim() || !wsRef.current || !isConnected) return;

    const payload = {
      text: inputValue,
      target: selectedAgent ? selectedAgent.id : 'global', 
      timestamp: new Date().toISOString()
    };

    wsRef.current.send(JSON.stringify(payload));
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
              {selectedAgent ? `Logs: ${selectedAgent.name}` : "Global Logs"}
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
            {selectedAgent ? selectedAgent.name : "All Agents"}
          </Button>
        </div>

        {/* 2. СЕКЦИЯ ЛОГОВ */}
        <div className="flex-1 min-h-0 relative"> 
          <ScrollArea className="h-full w-full"> 
            <div className="p-4 space-y-3 font-mono text-[11px] leading-relaxed">
              {filteredEvents.map((event) => (
                <div key={event.id} className={`animate-in fade-in slide-in-from-bottom-1 duration-300 border-l-2 pl-2 ${
                  event.type === 'error' ? 'border-red-500/50' : 
                  event.type === 'system' ? 'border-yellow-500/50' : 'border-primary/20'
                }`}>
                  <div className="flex items-baseline gap-2 mb-0.5">
                    <span className="text-primary/60 text-[10px]">[{event.timestamp}]</span>
                    {event.type === 'error' && <span className="text-red-400 font-bold uppercase text-[9px]">Error</span>}
                    {event.type === 'system' && <span className="text-yellow-400 font-bold uppercase text-[9px]">System</span>}
                  </div>
                  <div className={`break-all whitespace-pre-wrap ${
                    event.type === 'error' ? 'text-red-300' : 
                    event.type === 'system' ? 'text-yellow-200/80' : 'text-muted-foreground'
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
        <div className="p-3 bg-muted/20 shrink-0 h-auto">
          <div className="mb-2 text-[10px] uppercase font-semibold text-muted-foreground px-1 flex justify-between">
            <span>{selectedAgent ? `Private: ${selectedAgent.name}` : "Global Broadcast"}</span>
            <span className={isConnected ? "text-green-600" : "text-red-600"}>
                {isConnected ? "ONLINE" : "OFFLINE"}
            </span>
          </div>
          <div className="relative flex items-center">
            <Input 
              disabled={!isConnected}
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={isConnected ? "Send message..." : "Waiting for connection..."} 
              className="pr-10 bg-background/50 border-muted focus-visible:ring-primary/30"
            />
            <Button 
                size="icon" 
                variant="ghost" 
                className="absolute right-0 h-full text-primary"
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
            <CommandItem onSelect={() => { setSelectedAgent(null); setOpen(false); }} className="cursor-pointer font-bold text-primary">
              <User className="mr-2 h-4 w-4" />
              <span>All Agents (Global Chat)</span>
            </CommandItem>
          </CommandGroup>
          <CommandGroup heading="Individual Agents">
            {agents.map((agent) => (
              <CommandItem key={agent.id} onSelect={() => { setSelectedAgent(agent); setOpen(false); }} className="cursor-pointer">
                <User className="mr-2 h-4 w-4 opacity-50" />
                <span>{agent.name}</span>
                <span className="ml-auto text-[10px] opacity-40">{agent.role}</span>
              </CommandItem>
            ))}
          </CommandGroup>
        </CommandList>
      </CommandDialog>
    </>
  )
}