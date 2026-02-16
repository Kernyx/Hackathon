package com.nikguscode.aiagentservice.aiagent.application;

import com.nikguscode.aiagentservice.aiagent.domain.models.AiAgent;
import com.nikguscode.aiagentservice.aiagent.domain.models.AiAgentRepository;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

@Service
@RequiredArgsConstructor
public class AiAgentUsecase {
  private final AiAgentRepository aiAgentRepository;

  public void registerAgent(AiAgentCommand command) {
    AiAgent agent = AiAgent.createAgent(command);
    System.out.println(agent);
    aiAgentRepository.save(agent);
  }

  public void removeAgent(UUID aiAgentId) {
    aiAgentRepository.delete(aiAgentId);
  }

  public void updateAgent(AiAgentCommand command, UUID agentId) {
    AiAgent agent = AiAgent.createAgent(command);
    aiAgentRepository.update(agent, agentId);
  }

  public AiAgent findAgent(UUID aiAgentId) {
    Optional<AiAgent> aiAgentOpt = aiAgentRepository.findById(aiAgentId);

    if (aiAgentOpt.isEmpty()) {
      throw new RuntimeException("заглушка");
    }

    return aiAgentOpt.get();
  }

  public List<AiAgent> findAgentsByUserId(UUID userId) {
    return aiAgentRepository.findByUserId(userId);
  }
}
