package com.nikguscode.aiagentservice.aiagent.domain.models;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

public interface AiAgentRepository {
  void save(AiAgent aiAgent);

  void delete(UUID aiAgentId);

  Optional<AiAgent> findById(UUID aiAgentId);

  List<AiAgent> findByUserId(UUID userId);
}