package com.nikguscode.aiagentservice.aiagent.infrastructure.jooq;

import static com.nikguscode.aiagentservice.jooq.tables.AiAgent.AI_AGENT;

import com.nikguscode.aiagentservice.aiagent.domain.models.AiAgent;
import com.nikguscode.aiagentservice.aiagent.domain.models.AiAgentRepository;
import com.nikguscode.aiagentservice.aiagent.infrastructure.mapper.AiAgentJooqMapper;
import com.nikguscode.aiagentservice.jooq.tables.records.AiAgentRecord;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import lombok.RequiredArgsConstructor;
import org.jooq.DSLContext;
import org.springframework.stereotype.Service;
import tools.jackson.databind.ObjectMapper;

@Service
@RequiredArgsConstructor
public class JooqAiAgentRepository implements AiAgentRepository {
  private final DSLContext dsl;
  private final AiAgentJooqMapper aiAgentJooqMapper;
  private final ObjectMapper objectMapper;

  @Override
  public void save(AiAgent agent) {
    AiAgentRecord record = dsl.newRecord(AI_AGENT);
    aiAgentJooqMapper.updateRecordFromDomain(agent, record);
    record.store();
  }

  @Override
  public void delete(UUID aiAgentId) {
    dsl
        .delete(AI_AGENT)
        .where(AI_AGENT.ID.eq(aiAgentId))
        .execute();
  }

  @Override
  public Optional<AiAgent> findById(UUID aiAgentId) {
    return dsl
        .selectFrom(AI_AGENT)
        .where(AI_AGENT.ID.eq(aiAgentId))
        .fetchOptional()
        .map(aiAgentJooqMapper::toDomain);
  }

  @Override
  public List<AiAgent> findByUserId(UUID userId) {
    return dsl
        .selectFrom(AI_AGENT)
        .where(AI_AGENT.USER_ID.eq(userId))
        .fetch()
        .map(aiAgentJooqMapper::toDomain);
  }
}