package com.nikguscode.aiagentservice.aiagent.api.controller;

import com.nikguscode.aiagentservice.aiagent.api.dto.AgentCreateDto;
import com.nikguscode.aiagentservice.aiagent.api.mapper.AgentMapper;
import com.nikguscode.aiagentservice.aiagent.application.AiAgentSnapshot;
import com.nikguscode.aiagentservice.aiagent.application.AiAgentUsecase;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RequiredArgsConstructor
@RequestMapping("api/v1/ai-agent")
@RestController
public class AiAgentController {
  private final AgentMapper mapper;
  private final AiAgentUsecase aiAgentUsecase;

  @PostMapping("/ai-agents")
  public ResponseEntity<String> createAiAgent(@RequestBody @Validated AgentCreateDto dto) {
    System.out.println(dto);
    AiAgentSnapshot snapshot = mapper.toSnapshot(dto);
    System.out.println(snapshot);
    aiAgentUsecase.registerAgent(snapshot);
    return ResponseEntity.status(HttpStatus.CREATED).body("ok");
  }
}