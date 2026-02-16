package com.nikguscode.aiagentservice.aiagent.infrastructure.jooq;

import static com.nikguscode.aiagentservice.jooq.tables.AiAgent.AI_AGENT;

import com.nikguscode.aiagentservice.aiagent.domain.models.AiAgent;
import com.nikguscode.aiagentservice.aiagent.domain.models.AiAgentRepository;
import com.nikguscode.aiagentservice.jooq.tables.records.AiAgentRecord;
import lombok.RequiredArgsConstructor;
import org.jooq.DSLContext;
import org.jooq.JSONB;
import org.springframework.stereotype.Service;
import tools.jackson.core.JacksonException;
import tools.jackson.databind.ObjectMapper;

@Service
@RequiredArgsConstructor
public class JooqAiAgentRepository implements AiAgentRepository {
  private final DSLContext dsl;
  private final ObjectMapper objectMapper;

  @Override
  public void save(AiAgent agent) {
    AiAgentRecord record = fillRecord(agent);

    try {
      String jsonTraits = objectMapper.writeValueAsString(agent.getTraits());
      record.setTraits(JSONB.valueOf(jsonTraits));
    } catch (JacksonException e) {
      throw new RuntimeException("Не удалось запаковать traits в JSON", e);
    }

    record.store();
  }

  private AiAgentRecord fillRecord(AiAgent agent) {
    AiAgentRecord record = dsl.newRecord(AI_AGENT);

    record.setId(agent.getId());
    record.setUsername(agent.getUsername());
    record.setPhoto(agent.getPhotoLink());
    record.setIsMale(agent.getIsMale());
    record.setAge(agent.getAge());
    record.setInterests(agent.getInterests());
    record.setAdditionalInformation(agent.getAdditionalInformation());
    record.setPersonalityType(
        com.nikguscode.aiagentservice.jooq.enums.PersonalityType
            .valueOf(agent.getPersonalityType().name()));

    return record;
  }
}