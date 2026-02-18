import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { AgentDrawer, type AgentData } from "./AgentDrawer"
import { deleteAgentFromStorage, getStoredAgents, LS_KEY } from "@/lib/storage";
import { Badge } from "@/components/ui/badge"
import { Plus } from "lucide-react"
import { useEffect, useRef, useState } from "react"
import type { MouseEvent } from "react"
import { Trash2, Undo2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { AiAgentServiceService } from "../../api/services/AiAgentServiceService"
import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"

// Безопасная функция для извлечения характеристик (traits)
const extractTraits = (res: any) => {
  // 1. Если сервер отдал нормальный объект traits (как в новом JSON)
  if (res.traits && typeof res.traits === 'object') {
    return res.traits;
  }

  // 2. Если вдруг traits или additionalInformation пришли как JSON-строка (старый формат)
  const stringToParse = typeof res.traits === 'string'
    ? res.traits
    : typeof res.additionalInformation === 'string'
      ? res.additionalInformation
      : null;

  if (stringToParse) {
    try {
      const parsed = JSON.parse(stringToParse);
      // Проверяем, что распарсился именно объект, а не число/буль
      if (parsed && typeof parsed === 'object') {
        return parsed;
      }
    } catch (e) {
      // Это обычный текст (например: "Пишет стихи..."). Игнорируем ошибку.
    }
  }

  // 3. Дефолтное значение, если ничего не подошло
  return { openness: 50, conscientiousness: 50, extraversion: 50, agreeableness: 50, neuroticism: 50 };
};

export function SectionCards({ externalAgents }: { externalAgents?: any[] }) {
  const [agents, setAgents] = useState<AgentData[]>([]);
  const [selectedAgent, setSelectedAgent] = useState<AgentData | null>(null);
  const [pendingDelete, setPendingDelete] = useState<Set<string>>(new Set());
  const deleteTimersRef = useRef<Map<string, number>>(new Map());
  const pendingDeleteRef = useRef<Set<string>>(new Set());

  // Маппинг внешних агентов
  useEffect(() => {
    if (externalAgents && externalAgents.length > 0) {
      const formatted = externalAgents.map((res: any) => ({
        id: res.id,
        name: res.username,
        avatarSeed: res.photo || res.photoLink, // Учли photoLink из твоего JSON
        age: res.age,
        role: res.personalityType,
        traits: extractTraits(res),
      }));
      setAgents(formatted);
    }
  }, [externalAgents]);

  useEffect(() => {
    pendingDeleteRef.current = pendingDelete;
  }, [pendingDelete]);

  const handleDeleteRequest = async (e: MouseEvent, id: string) => {
    try {
      e.stopPropagation();
      await AiAgentServiceService.deleteAiAgentAgents(id);
      deleteAgentFromStorage(id);
      setPendingDelete((prev) => new Set(prev).add(id));
    } catch (error) {
      console.error("Ошибка при удалении:", error);
    }
  };

  const handleMouseLeave = (id: string) => {
    if (pendingDelete.has(id)) {
      if (deleteTimersRef.current.has(id)) return;

      const timerId = window.setTimeout(() => {
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
        deleteTimersRef.current.delete(id);
      }, 2000);

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

  // Получение с сервера
  useEffect(() => {
    const fetchAgentsFromServer = async () => {
      const localData = getStoredAgents();
      if (localData.length > 0) setAgents(localData);

      const userId = localStorage.getItem('userId');
      if (!userId) return;

      try {
        const relations = await AiAgentServiceService.getAiAgentUsersAgentsRelations(userId);

        if (!relations || relations.length === 0) {
          setAgents([]);
          localStorage.setItem(LS_KEY, JSON.stringify([]));
          return;
        }

        const agentDetailsPromises = relations.map((rel: any) =>
          AiAgentServiceService.getAiAgentAgents(rel.agentId)
        );

        const agentsRawData = await Promise.all(agentDetailsPromises);

        const formattedAgents: AgentData[] = agentsRawData.map((res: any) => ({
          id: res.id,
          name: res.username,
          avatarSeed: res.photo || res.photoLink, // Учли photoLink
          age: res.age,
          male: res.isMale,
          role: res.personalityType,
          interests: res.interests,
          traits: extractTraits(res), // Использовали безопасную функцию
          ownerId: userId
        }));

        setAgents(formattedAgents);
        localStorage.setItem(LS_KEY, JSON.stringify(formattedAgents));
        localStorage.setItem('all_agents_catalog', JSON.stringify(formattedAgents));

      } catch (error) {
        console.error("Ошибка при синхронизации:", error);
      }
    };

    fetchAgentsFromServer();
  }, []);

  const handleAddNew = () => {
    const newAgent: AgentData = {
      id: crypto.randomUUID(),
      name: "",
      avatarSeed: Math.random().toString(36).substring(7),
      male: true,
      role: "Custom",
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
              {isDeleting && (
                <div className="absolute inset-0 z-10 flex items-center justify-between px-4 bg-background/90 backdrop-blur-[2px] animate-in fade-in duration-300">
                  <span className="text-xs font-medium text-gray-200">Агент будет удален...</span>
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-8 gap-2 border-primary/20 hover:bg-primary/10"
                    onClick={(e) => handleUndo(e, agent.id!)}
                  >
                    <Undo2 className="h-3 w-3 text-gray-200" /> Отмена
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

                {!isDeleting && (
                  <div className="ml-auto flex items-center gap-2">
                    {agent.mood && (
                       <Badge variant="outline" className={`group-hover:hidden ${agent.mood === 'angry' ? 'border-red-500 text-red-500 bg-red-500/10' : ''}`}>
                         {agent.mood}
                       </Badge>
                    )}

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
            </Card>
          );
        })}

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