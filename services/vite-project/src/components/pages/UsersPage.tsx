import AgentGraph from "../AgentGraph"
import { SideConsole } from "../SideConsole"
import { AgentStreamProvider } from "@/lib/agent-stream/AgentStreamContext"
export default function UsersPage() {
    return (
        <AgentStreamProvider>
            <div className="flex h-full w-full overflow-hidden bg-background">
            
            <main className="relative flex-1 min-w-0 h-full">
                <div className="absolute inset-0">
                <AgentGraph />
                </div>
            </main>
            
            <div className="hidden xl:flex  shrink-0 bg-card">
                <SideConsole />
            </div>
            </div>
        </AgentStreamProvider>
    );
}

