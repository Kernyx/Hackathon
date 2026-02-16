package com.nikguscode.aiagentservice.aiagent.api.mapper;

import com.nikguscode.aiagentservice.aiagent.api.dto.AgentCreateDto;
import com.nikguscode.aiagentservice.aiagent.application.AiAgentSnapshot;
import org.mapstruct.Mapper;

@Mapper(componentModel = "spring")
public interface AiAgentWebMapper {
  AiAgentSnapshot toSnapshot(AgentCreateDto dto);
}