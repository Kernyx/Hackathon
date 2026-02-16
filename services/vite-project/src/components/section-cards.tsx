import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { AgentDrawer, type AgentData } from "./AgentDrawer" // Импортируем тип
import { getStoredAgents } from "@/lib/storage";
import { Badge } from "@/components/ui/badge"
import { Plus } from "lucide-react"
import { useState } from "react"
import { useEffect } from "react";
import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"

export function SectionCards() {
  const [agents, setAgents] = useState<AgentData[]>([]);
  const [selectedAgent, setSelectedAgent] = useState<AgentData | null>(null);

  useEffect(() => {
        setAgents(getStoredAgents());
    }, []);

  const emptyAgent: AgentData = { 
        name: "", 
        avatarSeed: "Alex", 
        male: true,
        role: "Analyst", 
        mood: "neutral", 
        age: "", 
        interests: "",
        traits: { openness: 50, conscientiousness: 50, extraversion: 50, agreeableness: 50, neuroticism: 50 }
    };

  const refreshData = () => {
          setAgents(getStoredAgents());
          setSelectedAgent(null);
  };



  return (

    <>

      <div className="grid grid-cols-1 gap-4 px-4 lg:px-6 @xl/main:grid-cols-2 @5xl/main:grid-cols-4">
        {agents.map((agent) => (

          <Card

            key={agent.id}

            className="group cursor-pointer transition-all hover:ring-2 hover:ring-primary/50 active:scale-95 @container/card bg-linear-to-t from-primary/5 to-card dark:bg-card shadow-xs"

            onClick={() => setSelectedAgent(agent)}

          >

            <CardHeader className="flex flex-row items-center gap-4 space-y-0">

              {/* Если ты используешь selectedAvatar для генерации картинки, используй agent.name или спец поле */}

              <Avatar className="h-12 w-12 border-2 border-background shadow-sm">

                <AvatarImage src={`https://api.dicebear.com/7.x/notionists/svg?seed=${agent.avatarSeed}`} />

                <AvatarFallback>{agent.name[0]}</AvatarFallback>

              </Avatar>

              <div className="flex flex-col gap-1">

                <CardTitle className="text-xl font-semibold leading-none group-hover:text-primary transition-colors">

                  {agent.name}

                </CardTitle>

                <CardDescription className="text-xs">{agent.role}</CardDescription>

              </div>

              <div className="ml-auto">

                <Badge variant="outline" className={`${agent.mood === 'angry' ? 'border-red-500 text-red-500 bg-red-500/10' : ''}`}>

                  {agent.mood}

                </Badge>

              </div>

            </CardHeader>

          </Card>

        ))}



        {/* Кнопка Добавить */}

        <Card

          className="flex items-center justify-center border-2 border-dashed border-muted-foreground/20 bg-transparent hover:bg-muted/50 hover:border-primary/50 cursor-pointer transition-all h-24.5"

          onClick={() => setSelectedAgent(emptyAgent)}

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