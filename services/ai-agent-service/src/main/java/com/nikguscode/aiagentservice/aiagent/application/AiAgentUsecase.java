package com.nikguscode.aiagentservice.aiagent.application;

import com.nikguscode.aiagentservice.aiagent.domain.models.AiAgent;
import com.nikguscode.aiagentservice.aiagent.domain.models.AiAgentRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

@Service
@RequiredArgsConstructor
public class AiAgentUsecase {
  private final AiAgentRepository aiAgentRepository;

  public void registerAgent(AiAgentSnapshot snapshot) {
    AiAgent agent = AiAgent.createAgent(snapshot);
    aiAgentRepository.save(agent);
  }

  public void removeAgent() {

  }
}
