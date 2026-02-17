import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { AgentDrawer, type AgentData } from "./AgentDrawer" // Импортируем тип
import { deleteAgentFromStorage, getStoredAgents } from "@/lib/storage";
import { Badge } from "@/components/ui/badge"
import { Plus } from "lucide-react"
import { useEffect, useRef, useState } from "react"
import type { MouseEvent } from "react"
import { Trash2, Undo2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"

export function SectionCards() {
  const [agents, setAgents] = useState<AgentData[]>([]);
  const [selectedAgent, setSelectedAgent] = useState<AgentData | null>(null);
  const [pendingDelete, setPendingDelete] = useState<Set<string>>(new Set());
  const deleteTimersRef = useRef<Map<string, number>>(new Map());
  const pendingDeleteRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    pendingDeleteRef.current = pendingDelete;
  }, [pendingDelete]);

  const handleDeleteRequest = (e: MouseEvent, id: string) => {
    e.stopPropagation();
    setPendingDelete((prev) => new Set(prev).add(id));
  };

  const handleMouseLeave = (id: string) => {
    if (pendingDelete.has(id)) {
      // Не ставим второй таймер на тот же id
      if (deleteTimersRef.current.has(id)) return;

      // Если пользователь увел мышку с "удаляемой" карточки, 
      // даем ему 1.5 - 2 секунды передумать и удаляем окончательно
      const timerId = window.setTimeout(() => {
        // Удаляем только если "Отмена" всё ещё показывается (т.е. не отменили)
        if (pendingDeleteRef.current.has(id)) {
          deleteAgentFromStorage(id);
          refreshData();
          setPendingDelete((prev) => {
            if (!prev.has(id)) return prev;
            const next = new Set(prev);
            next.delete(id);
            return next;
          });
        }

        // Таймер отработал — чистим ссылку
        deleteTimersRef.current.delete(id);
      }, 2000); // Время на "подумать" после отвода курсора

      deleteTimersRef.current.set(id, timerId);
    }
  };

  const handleUndo = (e: MouseEvent, id: string) => {
    e.stopPropagation();

    const t = deleteTimersRef.current.get(id);
    if (t) {
      window.clearTimeout(t);
      deleteTimersRef.current.delete(id);
    }

    setPendingDelete((prev) => {
      const newSet = new Set(prev);
      newSet.delete(id);
      return newSet;
    });
  };

  useEffect(() => {
        setAgents(getStoredAgents());
    }, []);

  const handleAddNew = () => {
    const newAgent: AgentData = {
      id: crypto.randomUUID(), 
      name: "",
      avatarSeed: Math.random().toString(36).substring(7), // Рандомный сид для интереса
      male: true,
      role: "Analyst",
      mood: "neutral",
      age: "",
      interests: "",
      traits: { openness: 50, conscientiousness: 50, extraversion: 50, agreeableness: 50, neuroticism: 50 }
    };
    setSelectedAgent(newAgent);
  };

  const refreshData = () => {
          setAgents(getStoredAgents());
          setSelectedAgent(null);
  };



  return (

    <>

      <div className="grid grid-cols-1 gap-4 px-4 lg:px-6 @xl/main:grid-cols-2 @5xl/main:grid-cols-4">
        {agents.map((agent) => {
          const isDeleting = pendingDelete.has(agent.id!);

          return (
            <Card
              key={agent.id}
              onMouseLeave={() => handleMouseLeave(agent.id!)}
              className={`group relative overflow-hidden cursor-pointer transition-all @container/card shadow-xs
                ${isDeleting 
                  ? "opacity-50 grayscale scale-95 border-destructive/50 bg-destructive/5" 
                  : "hover:ring-2 hover:ring-primary/50 active:scale-95 bg-linear-to-t from-primary/5 to-card"}
              `}
              onClick={() => !isDeleting && setSelectedAgent(agent)}
            >
              {/* Слой удаления (Overlay) */}
              {isDeleting && (
                <div className="absolute inset-0 z-10 flex items-center justify-between px-4 bg-background/80 backdrop-blur-[2px] animate-in fade-in duration-300">
                  <span className="text-xs font-medium text-destructive">Агент будет удален...</span>
                  <Button 
                    variant="outline" 
                    size="sm" 
                    className="h-8 gap-2 border-primary/20 hover:bg-primary/10"
                    onClick={(e) => handleUndo(e, agent.id!)}
                  >
                    <Undo2 className="h-3 w-3" /> Отмена
                  </Button>
                </div>
              )}

              <CardHeader className="flex flex-row items-center gap-4 space-y-0 relative">
                <Avatar className="h-12 w-12 border-2 border-background shadow-sm">
                  <AvatarImage src={`https://api.dicebear.com/7.x/notionists/svg?seed=${agent.avatarSeed}`} />
                  <AvatarFallback>{agent.name ? agent.name[0] : "?"}</AvatarFallback>
                </Avatar>

                <div className="flex flex-col gap-1">
                  <CardTitle className="text-xl font-semibold leading-none group-hover:text-primary transition-colors">
                    {agent.name}
                  </CardTitle>
                  <CardDescription className="text-xs">{agent.role}</CardDescription>
                </div>

                {/* Кнопка удаления - появляется при ховере */}
                {!isDeleting && (
                  <div className="ml-auto flex items-center gap-2">
                    <Badge variant="outline" className={`group-hover:hidden ${agent.mood === 'angry' ? 'border-red-500 text-red-500 bg-red-500/10' : ''}`}>
                      {agent.mood}
                    </Badge>
                    
                    <Button
                      variant="ghost"
                      size="icon"
                      className="hidden group-hover:flex h-8 w-8 text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-all"
                      onClick={(e) => handleDeleteRequest(e, agent.id!)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                )}
              </CardHeader>
              
              {/* Прогресс-бар удаления (опционально) */}
              {isDeleting && (
                <div className="absolute bottom-0 left-0 h-1 bg-destructive animate-shrink-x" style={{ width: '100%' }} />
              )}
            </Card>
          );
        })}



        {/* Кнопка Добавить */}

        <Card

          className="flex items-center justify-center border-2 border-dashed border-muted-foreground/20 bg-transparent hover:bg-muted/50 hover:border-primary/50 cursor-pointer transition-all h-24.5"

          onClick={handleAddNew}

        >

          <div className="flex flex-col items-center gap-1 text-muted-foreground group-hover:text-primary">

            <Plus className="h-6 w-6" />

            <span className="text-[10px] font-medium uppercase tracking-wider">Добавить</span>

          </div>

        </Card>

      </div>



      {/* Drawer */}

    {selectedAgent && (
                    <AgentDrawer 
                        agent={selectedAgent}
                        open={!!selectedAgent}
                        onOpenChange={(open) => !open && setSelectedAgent(null)}
                        onSaveSuccess={refreshData} 
                    />
    )}

    </>

  )

}