package com.nikguscode.aiagentservice.aiagent.infrastructure.mapper;

import com.nikguscode.aiagentservice.aiagent.domain.models.AiAgentTraits;
import lombok.RequiredArgsConstructor;
import org.jooq.JSONB;
import org.springframework.stereotype.Component;
import tools.jackson.databind.ObjectMapper;

@Component
@RequiredArgsConstructor
public class AiAgentJsonHelpers {
  private final ObjectMapper objectMapper;

  public JSONB toJsonb(AiAgentTraits t) {
    if (t == null) {
      return null;
    }

    try {
      return JSONB.valueOf(objectMapper.writeValueAsString(t));
    } catch (Exception e) {
      throw new RuntimeException(e);
    }
  }

  public AiAgentTraits fromJsonb(JSONB j) {
    if (j == null) {
      return null;
    }
    try {
      return objectMapper.readValue(j.data(), AiAgentTraits.class);
    } catch (Exception e) {
      throw new RuntimeException(e);
    }
  }
}
