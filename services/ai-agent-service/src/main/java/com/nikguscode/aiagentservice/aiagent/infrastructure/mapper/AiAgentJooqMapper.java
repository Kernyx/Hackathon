package com.nikguscode.aiagentservice.aiagent.infrastructure.mapper;

import com.nikguscode.aiagentservice.aiagent.domain.models.AiAgent;
import com.nikguscode.aiagentservice.aiagent.domain.models.AiAgentTraits;
import com.nikguscode.aiagentservice.aiagent.domain.models.PersonalityType;
import com.nikguscode.aiagentservice.jooq.tables.records.AiAgentRecord;
import java.util.Objects;
import org.mapstruct.Mapper;
import org.mapstruct.MappingTarget;
import org.springframework.beans.factory.annotation.Autowired;

@Mapper(componentModel = "spring")
public abstract class AiAgentJooqMapper {
  @Autowired
  protected AiAgentJsonHelpers jsonHelpers;

  public abstract AiAgentRecord toRecord(AiAgent aiAgent);

  public void updateRecordFromDomain(AiAgent domain, @MappingTarget AiAgentRecord record) {
    if (!Objects.equals(record.getUserId(), domain.getUserId())) {
      record.setUserId(domain.getUserId());
    }

    if (!Objects.equals(record.getUsername(), domain.getUsername())) {
      record.setUsername(domain.getUsername());
    }

    if (!Objects.equals(record.getPhotoLink(), domain.getPhotoLink())) {
      record.setPhotoLink(domain.getPhotoLink());
    }

    if (!Objects.equals(record.getIsMale(), domain.getIsMale())) {
      record.setIsMale(domain.getIsMale());
    }

    if (!Objects.equals(record.getAge(), domain.getAge())) {
      record.setAge(domain.getAge());
    }

    if (!Objects.equals(record.getInterests(), domain.getInterests())) {
      record.setInterests(domain.getInterests());
    }

    if (!Objects.equals(record.getAdditionalInformation(), domain.getAdditionalInformation())) {
      record.setAdditionalInformation(domain.getAdditionalInformation());
    }

    var newPersonality = map(domain.getPersonalityType());
    if (!Objects.equals(record.getPersonalityType(), newPersonality)) {
      record.setPersonalityType(newPersonality);
    }

    var newTraitsJson = map(domain.getTraits());
    if (!Objects.equals(record.getTraits(), newTraitsJson)) {
      record.setTraits(newTraitsJson);
    }
  }

  public AiAgent toDomain(AiAgentRecord record) {
    if (record == null) {
      return null;
    }

    return AiAgent.restore(
        record.getId(),
        record.getUserId(),
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