import React, { useEffect, useState } from "react"
import { SectionCards } from "@/components/section-cards"
import { OpenAPI } from "../../../api/core/OpenAPI";
import { AiAgentServiceService } from "../../../api/services/AiAgentServiceService";
import { getAgentsFromStorage, saveAgentsToStorage } from "@/lib/storage";

export default function AgentPage() {
  const [agents, setAgents] = useState([]);
  const userId = localStorage.getItem("userId");

  useEffect(() => {
    const fetchAgents = async () => {
      // ← ИСПРАВЛЕНО: Убран лишний пробел в конце URL
      const MY_DOMAIN = "https://api.besthackaton.duckdns.org/api/v1";
      OpenAPI.BASE = MY_DOMAIN;

      if (!userId) {
        console.warn("No userId found in localStorage");
        // Пытаемся загрузить из storage даже без userId (для оффлайн режима)
        const localAgents = getAgentsFromStorage();
        if (localAgents) setAgents(localAgents);
        return;
      }

      try {
        const data = await AiAgentServiceService.getAiAgentUsersAgents(userId);

        if (data) {
          // ← ИСПРАВЛЕНО: Опечатка в setAgents
          setAgents(data);
          saveAgentsToStorage(data);
        }
      } catch (error) {
        console.error("API Error: ", error);
        const localAgents = getAgentsFromStorage();
        if (localAgents) {
          setAgents(localAgents);
        }
      }
    };

    fetchAgents();
  }, [userId]);

  return (
    <>
      <div className="flex flex-1 flex-col">
        <div className="@container/main flex flex-1 flex-col gap-2">
          <div className="flex flex-1 flex-col gap-4 py-4 md:gap-6 md:py-6">
            <SectionCards externalAgents={agents} />
          </div>
        </div>
      </div>
    </>
  )
}