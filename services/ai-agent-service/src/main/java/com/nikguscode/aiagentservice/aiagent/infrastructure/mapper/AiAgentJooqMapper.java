package com.nikguscode.aiagentservice.aiagent.infrastructure.mapper;

import com.nikguscode.aiagentservice.aiagent.domain.models.AiAgent;
import com.nikguscode.aiagentservice.aiagent.domain.models.AiAgentTraits;
import com.nikguscode.aiagentservice.aiagent.domain.models.PersonalityType;
import com.nikguscode.aiagentservice.jooq.tables.records.AiAgentRecord;
import org.mapstruct.Mapper;
import org.mapstruct.MappingTarget;
import org.springframework.beans.factory.annotation.Autowired;

@Mapper(componentModel = "spring")
public abstract class AiAgentJooqMapper {
  @Autowired
  protected AiAgentJsonHelpers jsonHelpers;

  public abstract AiAgentRecord toRecord(AiAgent aiAgent);

  public abstract void updateRecordFromDomain(AiAgent source, @MappingTarget AiAgentRecord target);

  public AiAgent toDomain(AiAgentRecord record) {
    if (record == null) {
      return null;
    }

    return AiAgent.restore(
        record.getId(),
        record.getUsername(),
        record.getPhotoLink(),
        Boolean.TRUE.equals(record.getIsMale()),
        record.getAge(),
        record.getInterests(),
        map(record.getPersonalityType()),
        jsonHelpers.fromJsonb(record.getTraits()),
        record.getAdditionalInformation()
    );
  }

  protected org.jooq.JSONB map(AiAgentTraits traits) {
    return jsonHelpers.toJsonb(traits);
  }

  protected AiAgentTraits map(org.jooq.JSONB jsonb) {
    return jsonHelpers.fromJsonb(jsonb);
  }

  protected PersonalityType map(com.nikguscode.aiagentservice.jooq.enums.PersonalityType p) {
    return p == null ? null : PersonalityType.valueOf(p.name());
  }

  protected com.nikguscode.aiagentservice.jooq.enums.PersonalityType map(PersonalityType p) {
    return p == null ?
        null : com.nikguscode.aiagentservice.jooq.enums.PersonalityType.valueOf(p.name());
  }
}