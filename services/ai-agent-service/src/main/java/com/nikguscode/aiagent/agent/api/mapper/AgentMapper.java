package com.nikguscode.aiagent.agent.api.mapper;

import com.nikguscode.aiagent.agent.api.dto.AgentCreateDto;
import com.nikguscode.aiagent.agent.application.AgentSnapshot;
import org.mapstruct.Mapper;

@Mapper(componentModel = "spring")
public interface AgentMapper {
  AgentSnapshot toSnapshot(AgentCreateDto dto);
}