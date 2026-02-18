import AgentGraph from "../AgentGraph"
import { SideConsole } from "../SideConsole"
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { Label } from "../ui/label";
import { useState } from "react";

export default function UsersPage() {
    const [speed, setSpeed] = useState("");

    const handleSpeedChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const val = e.target.value;
        const onlyNumbers = val.replace(/\D/g, "");
        setSpeed(onlyNumbers); 
    };
    return (
        <div className="flex h-full w-full overflow-hidden bg-background">
        
        <main className="relative flex-1 min-w-0 h-full">
            <div className="absolute inset-0">
            <AgentGraph />
            </div>
        </main>
        
        <div className="hidden xl:flex  shrink-0 bg-card">
            <SideConsole />
        </div>
        <div className="toast toast-bottom flex flex-row items-center gap-2 p-4 bg-muted/30 border rounded-lg shadow-lg">
        <Input 
            id="speed" 
            value={speed}
            className="w-44" // Ограничиваем ширину инпута, чтобы не растягивался на весь экран
            onChange={handleSpeedChange}
            placeholder="Введите скорость..."
        />
        <Button className="px-4 py-2 h-10" onClick={() => console.log("Сохраняем скорость:", speed)}> {/* Стандартная высота h-10 хорошо сочетается с Input */}
            <span className="text-sm font-medium">Сохранить</span>
        </Button>
        </div>
        </div>
    );
}

