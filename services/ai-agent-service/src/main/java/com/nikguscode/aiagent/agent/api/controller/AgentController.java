package com.nikguscode.aiagent.agent.api.controller;

import com.nikguscode.aiagent.agent.api.dto.AgentCreateDto;
import com.nikguscode.aiagent.agent.api.mapper.AgentMapper;
import com.nikguscode.aiagent.agent.application.AgentSnapshot;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RequiredArgsConstructor
@RequestMapping("/api/v1/ai-agent")
@RestController
public class AgentController {
  private final AgentMapper mapper;

  @PostMapping("/ai-agents")
  public ResponseEntity<String> createAiAgent(AgentCreateDto dto) {
    AgentSnapshot snapshot = mapper.toSnapshot(dto);

    return null;
  }
}