import { MOCK_AGENTS } from "@/lib/mockData" 
import AgentGraph from "../AgentGraph"
import { SideConsole } from "../SideConsole"
import { useSidebar } from "@/components/ui/sidebar"
export default function UsersPage() {
  const { open } = useSidebar(); 

  const graphData = {
    nodes: MOCK_AGENTS,
    links: MOCK_AGENTS.flatMap((node, i) => 
      MOCK_AGENTS.slice(i + 1).map(target => ({ source: node.id, target: target.id }))
    )
  };
  
    return (
        // h-full заставит страницу занять ВСЁ место от хедера до футера, не больше и не меньше
        <div className="flex h-full w-full overflow-hidden bg-background">
        
        <main className="relative flex-1 min-w-0 h-full">
            {/* График на весь остаток экрана */}
            <div className="absolute inset-0">
            <AgentGraph data={graphData} />
            </div>
        </main>
        
        {/* Консоль теперь — жесткая колонка в флексе, как и сайдбар */}
        <div className="hidden xl:flex  shrink-0 bg-card">
            <SideConsole agents={MOCK_AGENTS} />
        </div>
        </div>
    );
}

