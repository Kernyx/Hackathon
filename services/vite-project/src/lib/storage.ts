import type { AgentData } from "../components/AgentDrawer";

export const LS_KEY = "ai_agents_data";
export const USER_ID_KEY = "userId";

// ← ДОБАВЛЕНО: Маппинг API → UI для localStorage
const API_ENUM_TO_UI_ROLE: Record<string, string> = {
  "INDIVIDUAL": "Custom",
  "ALTRUIST": "Analyst",
  "MACHIAVELLIAN": "Diplomat",
  "REBEL": "Aggressor",
  "STOIC": "Thinker"
};

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

export const saveAgentToStorage = (agent: AgentData) => {
  try {
    const existingData = localStorage.getItem(LS_KEY);
    const agents: AgentData[] = existingData ? JSON.parse(existingData) : [];
    const index = agents.findIndex((a) => a.id === agent.id);

    if (index !== -1) {
      agents[index] = { ...agents[index], ...agent };
    } else {
      agents.push(agent);
    }

    localStorage.setItem(LS_KEY, JSON.stringify(agents));
    console.log("✅ Agent saved to localStorage. Total agents:", agents.length);
  } catch (e) {
    console.error("❌ Error saving agent to storage:", e);
  }
};

export const saveAgentsToStorage = (agents: any[]) => {
  try {
    const syncedAgents = agents.map(agent => {
      // ← ИСПРАВЛЕНО: Маппим роль из API enum в UI роль при сохранении
      const rawRole = agent.role || agent.personalityType || "INDIVIDUAL";
      const mappedRole = API_ENUM_TO_UI_ROLE[rawRole] || rawRole;

      return {
        id: agent.id,
        name: agent.name || agent.username || "Без имени",
        avatarSeed: agent.avatarSeed || agent.photo || agent.photoLink || "Alex",
        age: agent.age,
        male: agent.male ?? agent.isMale ?? true,
        role: mappedRole,
        interests: agent.interests || "",
        traits: agent.traits || { openness: 50, conscientiousness: 50, extraversion: 50, agreeableness: 50, neuroticism: 50 },
        isSynced: true,
        mood: agent.mood || "neutral",
        ownerId: agent.ownerId || agent.userId
      };
    });

    localStorage.setItem(LS_KEY, JSON.stringify(syncedAgents));
    console.log("✅ Agents list saved to localStorage. Total:", syncedAgents.length);
  } catch (e) {
    console.error("❌ Error saving agents list to storage:", e);
  }
};

export const deleteAgentFromStorage = (id: string) => {
  try {
    const existingData = localStorage.getItem(LS_KEY);
    if (!existingData) return;
    const agents = JSON.parse(existingData) as AgentData[];
    const next = agents.filter((a) => a?.id !== id);
    localStorage.setItem(LS_KEY, JSON.stringify(next));
    console.log("✅ Agent deleted from localStorage. Remaining:", next.length);
  } catch (e) {
    console.error("❌ Error deleting agent from storage:", e);
  }
};