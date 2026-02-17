import type { AgentData } from "../components/AgentDrawer";

export const LS_KEY = "ai_agents_data";
export const USER_ID_KEY = "userId";

export const saveUserIdToStorage = (userId: string) => {
  if (typeof window === "undefined") return;
  localStorage.setItem(USER_ID_KEY, userId);
};

export const getStoredUserId = (): string | null => {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(USER_ID_KEY);
};

export const getStoredAgents = (): AgentData[] => {
  if (typeof window === "undefined") return [];
  const data = localStorage.getItem(LS_KEY);
  return data ? JSON.parse(data) : [];
};

export const saveAgentToStorage = (agent: any) => {
  try {
    // 1. Достаем старые данные
    const existingData = localStorage.getItem(LS_KEY);
    const agents = existingData ? JSON.parse(existingData) : [];
    
    if (!agent.ownerId) {
        agent.ownerId = localStorage.getItem(USER_ID_KEY);
    }
    // 2. Проверяем, нет ли уже агента с таким ID, чтобы не плодить дубликаты
    const index = agents.findIndex((a: any) => a.id === agent.id);
    
    if (index !== -1) {
      agents[index] = agent; // Обновляем
    } else {
      agents.push(agent); // Добавляем нового
    }
    
    // 3. Сохраняем обратно в строку
    localStorage.setItem(LS_KEY, JSON.stringify(agents));
    console.log("Записано в LocalStorage успешно!");
  } catch (e) {
    console.error("Ошибка записи в LS:", e);
  }
};

export const deleteAgentFromStorage = (id: string) => {
  try {
    const existingData = localStorage.getItem(LS_KEY);
    if (!existingData) return;

    const agents = JSON.parse(existingData) as Array<{ id?: string }>;
    const next = agents.filter((a) => a?.id !== id);
    localStorage.setItem(LS_KEY, JSON.stringify(next));
  } catch (e) {
    console.error("Ошибка удаления из LS:", e);
  }
};