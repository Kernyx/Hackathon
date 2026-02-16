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

// Интерфейс для сообщения
interface LogEvent {
  id: string;
  timestamp: string;
  data: any;
  type?: string; // system, error, chat, audit
}

export function SideConsole({ agents = [] }: { agents?: any[] }) {
  const [open, setOpen] = useState(false)
  const [selectedAgent, setSelectedAgent] = useState<any>(null)
  
  // -- STATE ДЛЯ WEBSOCKET --
  const [isConnected, setIsConnected] = useState(false)
  const [events, setEvents] = useState<LogEvent[]>([])
  const [inputValue, setInputValue] = useState("")
  const wsRef = useRef<WebSocket | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)

  // -- ПОДКЛЮЧЕНИЕ (аналог connect() из твоего HTML) --
  useEffect(() => {
    // Создаем подключение
    const ws = new WebSocket('ws://localhost:8083/api/v1/audit/ws');
    wsRef.current = ws;

    ws.onopen = () => {
      console.log('WebSocket connected');
      setIsConnected(true);
      addSystemMessage('System: Connected to audit stream');
    };

    ws.onmessage = (event) => {
      console.log('Message received:', event.data);
      try {
        // Пробуем распарсить JSON, как в твоем скрипте
        const parsedData = JSON.parse(event.data);
        addLogEvent(parsedData);
      } catch (e) {
        // Если пришла просто строка
        addLogEvent({ raw: event.data });
      }
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      addSystemMessage('System: Connection error', 'error');
    };

    ws.onclose = () => {
      console.log('WebSocket disconnected');
      setIsConnected(false);
      addSystemMessage('System: Disconnected', 'error');
    };

    // Cleanup при размонтировании компонента (аналог disconnect())
    return () => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.close();
      }
    };
  }, []);

  // -- ХЕЛПЕРЫ ДЛЯ ДОБАВЛЕНИЯ СООБЩЕНИЙ --
  
  const addLogEvent = (data: any, type: string = 'info') => {
    const newEvent: LogEvent = {
      id: crypto.randomUUID(),
      timestamp: new Date().toLocaleTimeString(),
      data: data,
      type: type
    };
    // Добавляем новые сообщения В НАЧАЛО (как в твоем HTML insertBefore), 
    // или В КОНЕЦ (стандартный чат). Здесь сделаем В НАЧАЛО (Newest top), 
    // чтобы соответствовать твоему примеру.
    setEvents(prev => [newEvent, ...prev]);
  };

  const addSystemMessage = (msg: string, type: string = 'system') => {
    addLogEvent({ message: msg }, type);
  }

  // -- ОТПРАВКА СООБЩЕНИЙ --
  const handleSendMessage = () => {
    if (!inputValue.trim() || !wsRef.current || !isConnected) return;

    const payload = {
      text: inputValue,
      // Если выбран агент, добавляем его ID, иначе 'broadcast'
      target: selectedAgent ? selectedAgent.id : 'global', 
      timestamp: new Date().toISOString()
    };

    // Отправляем JSON строку
    wsRef.current.send(JSON.stringify(payload));
    
    // Локально отображаем то, что отправили (опционально, зависит от бэкенда)
    // addLogEvent({ ...payload, sender: 'Me' }, 'outgoing'); 

    setInputValue("");
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSendMessage();
    }
  }

  // -- ФИЛЬТРАЦИЯ --
  // Если бэкенд шлет все подряд, фильтруем на фронте для выбранного агента.
  // Логика фильтрации зависит от структуры твоих данных. 
  // Здесь примерная логика: показываем всё, если агент не выбран.
  const filteredEvents = selectedAgent 
    ? events // Тут можно добавить .filter(), если в event.data есть agentId
    : events;

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
            {/* Индикатор статуса */}
            <div className={`h-2 w-2 rounded-full ${isConnected ? 'bg-green-500 shadow-[0_0_5px_#22c55e]' : 'bg-red-500'}`} title={isConnected ? "Connected" : "Disconnected"} />
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
          <ScrollArea className="h-full w-full" ref={scrollRef}> 
            <div className="p-4 space-y-3 font-mono text-[11px] leading-relaxed">
              
              {filteredEvents.length === 0 && (
                 <div className="text-center text-muted-foreground py-10 opacity-50">
                    Waiting for events...
                 </div>
              )}

              {filteredEvents.map((event) => (
                <div key={event.id} className="animate-in fade-in slide-in-from-top-1 duration-300 border-l-2 border-primary/20 pl-2">
                  <div className="flex items-baseline gap-2 mb-0.5">
                     <span className="text-primary/60 text-[10px]">[{event.timestamp}]</span>
                     {event.type === 'error' && <span className="text-red-400 font-bold">ERROR</span>}
                     {event.type === 'system' && <span className="text-yellow-400 font-bold">SYS</span>}
                  </div>
                  
                  {/* Рендеринг тела сообщения */}
                  <div className="text-muted-foreground break-all whitespace-pre-wrap">
                    {/* Если это объект, преобразуем красиво в строку, иначе выводим как есть */}
                    {typeof event.data === 'object' 
                      ? JSON.stringify(event.data, null, 2) 
                      : String(event.data)
                    }
                  </div>
                </div>
              ))}

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
              placeholder={isConnected ? (selectedAgent ? `Message ${selectedAgent.name}...` : "Send Text payload...") : "Connecting..."} 
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

      {/* МОДАЛКА ВЫБОРА (Без изменений) */}
      <CommandDialog open={open} onOpenChange={setOpen}>
        <CommandInput placeholder="Type a name or 'all'..." />
        <CommandList>
          <CommandEmpty>No results found.</CommandEmpty>
          
          <CommandGroup heading="General">
            <CommandItem 
              onSelect={() => {
                setSelectedAgent(null)
                setOpen(false)
              }}
              className="cursor-pointer font-bold text-primary"
            >
              <User className="mr-2 h-4 w-4" />
              <span>All Agents (Global Chat)</span>
            </CommandItem>
          </CommandGroup>

          <CommandGroup heading="Individual Agents">
            {agents.map((agent) => (
              <CommandItem 
                key={agent.id} 
                onSelect={() => {
                  setSelectedAgent(agent)
                  setOpen(false)
                }}
                className="cursor-pointer"
              >
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