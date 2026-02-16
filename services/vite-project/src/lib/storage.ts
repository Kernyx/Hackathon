import type { AgentData } from "@/components/AgentDrawer";

export const LS_KEY = "ai_agents_data";

export const getStoredAgents = (): AgentData[] => {
  if (typeof window === "undefined") return [];
  const data = localStorage.getItem(LS_KEY);
  return data ? JSON.parse(data) : [];
};

export const saveAgentToStorage = (agent: any) => {
  try {
    const key = "ai_agents_data"; // Убедись, что ключ именно такой
    // 1. Достаем старые данные
    const existingData = localStorage.getItem(key);
    const agents = existingData ? JSON.parse(existingData) : [];
    
    // 2. Проверяем, нет ли уже агента с таким ID, чтобы не плодить дубликаты
    const index = agents.findIndex((a: any) => a.id === agent.id);
    
    if (index !== -1) {
      agents[index] = agent; // Обновляем
    } else {
      agents.push(agent); // Добавляем нового
    }
    
    // 3. Сохраняем обратно в строку
    localStorage.setItem(key, JSON.stringify(agents));
    console.log("✅ Записано в LocalStorage успешно!");
  } catch (e) {
    console.error("❌ Ошибка записи в LS:", e);
  }
};