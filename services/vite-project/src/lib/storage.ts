// src/lib/storage.ts
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

export const getAgentsFromStorage = getStoredAgents;

// Сохранение одного агента (при создании/редактировании)
export const saveAgentToStorage = (agent: any) => {
  try {
    const existingData = localStorage.getItem(LS_KEY);
    const agents = existingData ? JSON.parse(existingData) : [];

    if (!agent.ownerId) {
      agent.ownerId = localStorage.getItem(USER_ID_KEY);
    }

    // Новые агенты помечаем как НЕ синхронизированные
    if (agent.isSynced === undefined) {
      agent.isSynced = false;
    }

    const index = agents.findIndex((a: any) => a.id === agent.id);

    if (index !== -1) {
      agents[index] = { ...agents[index], ...agent };
    } else {
      agents.push(agent);
    }

    localStorage.setItem(LS_KEY, JSON.stringify(agents));
  } catch (e) {
    console.error("Ошибка записи в LS:", e);
  }
};

// Сохранение всего списка (при загрузке с сервера)
export const saveAgentsToStorage = (agents: AgentData[]) => {
  try {
    // Помечаем все загруженные агенты как синхронизированные
    const syncedAgents = agents.map(agent => ({
      ...agent,
      isSynced: true
    }));
    localStorage.setItem(LS_KEY, JSON.stringify(syncedAgents));
  } catch (e) {
    console.error("Ошибка записи списка в LS:", e);
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