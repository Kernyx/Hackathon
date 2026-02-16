import React from "react"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { SendHorizontal, Terminal, User } from "lucide-react"
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command"

// Добавь пропс agents, чтобы консоль видела список
export function SideConsole({ agents = [] }: { agents?: any[] }) {
  const [open, setOpen] = React.useState(false)
  const [selectedAgent, setSelectedAgent] = React.useState<any>(null)

  return (
<>
      <aside className="fixed right-4 top-[10%] bottom-[10%] w-80 hidden xl:flex flex-col bg-card/80 backdrop-blur-md border border-border rounded-2xl shadow-2xl overflow-hidden z-40">
        
        {/* 1. ШАПКА */}
        <div className="h-14 flex items-center justify-between px-3 bg-muted/30 border-b border-border shrink-0">
          <div className="flex items-center gap-2">
            <Terminal className="h-4 w-4 text-primary" />
            <span className="text-[10px] font-bold uppercase tracking-widest opacity-70">
              {/* Если агент не выбран — пишем "All Messages" */}
              {selectedAgent ? `Logs: ${selectedAgent.name}` : "Global Logs"}
            </span>
          </div>

          <Button 
            variant="outline" 
            size="sm" 
            onClick={() => setOpen(true)}
            className="h-7 px-2 text-[11px] bg-background/50 border-muted gap-1.5"
          >
            <User className="h-3.5 w-3.5" />
            {/* Текст кнопки меняется в зависимости от выбора */}
            {selectedAgent ? selectedAgent.name : "All Agents"}
          </Button>
        </div>

        {/* 2. СЕКЦИЯ ЛОГОВ */}
        <div className="flex-1 min-h-0 relative"> 
          <ScrollArea className="h-full w-full"> 
            <div className="p-4 space-y-2 font-mono text-[11px] leading-relaxed">
              {/* ЛОГИКА ВЫВОДА */}
              {selectedAgent ? (
                // Если выбран конкретный агент — фильтруем (пока моками)
                Array.from({ length: 10 }).map((_, i) => (
                  <div key={i} className="text-muted-foreground animate-in fade-in duration-300">
                    <span className="text-primary">[{12 + i}:04:20]</span> {selectedAgent.name}: Specific data packet {i}...
                  </div>
                ))
              ) : (
                // Если выбран "Весь чат" — показываем сообщения от разных агентов вперемешку
                agents.map((agent, i) => (
                  <div key={agent.id + i} className="text-muted-foreground animate-in slide-in-from-left-1 duration-300">
                    <span className="text-primary/50">[{10 + i}:00:01]</span> <span className="text-primary">{agent.name}:</span> Broadcast message...
                  </div>
                ))
              )}
            </div>
          </ScrollArea>
        </div>

        <Separator />

        {/* 3. ЧАТ */}
        <div className="p-3 bg-muted/20 shrink-0 h-auto">
          <div className="mb-2 text-[10px] uppercase font-semibold text-muted-foreground px-1 text-center">
            {selectedAgent ? `Private: ${selectedAgent.name}` : "Global Broadcast"}
          </div>
          <div className="relative flex items-center">
            <Input 
              placeholder={selectedAgent ? `Message ${selectedAgent.name}...` : "Message all agents..."} 
              className="pr-10 bg-background/50 border-muted focus-visible:ring-primary/30"
            />
            <Button size="icon" variant="ghost" className="absolute right-0 h-full text-primary">
              <SendHorizontal className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </aside>

      {/* МОДАЛКА ВЫБОРА */}
      <CommandDialog open={open} onOpenChange={setOpen}>
        <CommandInput placeholder="Type a name or 'all'..." />
        <CommandList>
          <CommandEmpty>No results found.</CommandEmpty>
          
          <CommandGroup heading="General">
            {/* ПУНКТ "ВЕСЬ ЧАТ" */}
            <CommandItem 
              onSelect={() => {
                setSelectedAgent(null) // Сбрасываем в null для общего чата
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