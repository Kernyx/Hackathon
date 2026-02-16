package com.nikguscode.aiagentservice.aiagent.api.controller;

import com.nikguscode.aiagentservice.aiagent.api.dto.AgentCreateDto;
import com.nikguscode.aiagentservice.aiagent.api.mapper.AiAgentWebMapper;
import com.nikguscode.aiagentservice.aiagent.application.AiAgentSnapshot;
import com.nikguscode.aiagentservice.aiagent.application.AiAgentUsecase;
import com.nikguscode.aiagentservice.aiagent.domain.models.AiAgent;
import java.util.UUID;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RequiredArgsConstructor
@RequestMapping("api/v1/ai-agent")
@RestController
public class AiAgentController {
  private final AiAgentWebMapper mapper;
  private final AiAgentUsecase aiAgentUsecase;

  @PostMapping("/ai-agents")
  public ResponseEntity<String> createAiAgent(@RequestBody @Validated AgentCreateDto dto) {
    System.out.println(dto);
    AiAgentSnapshot snapshot = mapper.toSnapshot(dto);
    System.out.println(snapshot);
    aiAgentUsecase.registerAgent(snapshot);
    return ResponseEntity.status(HttpStatus.CREATED).body("ok");
  }

  @DeleteMapping("/agents/{agentId}")
  public ResponseEntity<String> deleteAiAgent(@PathVariable UUID agentId) {
    aiAgentUsecase.removeAgent(agentId);
    return ResponseEntity.status(HttpStatus.OK).body("Deleted");
  }

  @GetMapping("/agents/{agentId}")
  public ResponseEntity<AiAgent> getAiAgent(@PathVariable UUID agentId) {
    AiAgent agent = aiAgentUsecase.getAgent(agentId);
    return ResponseEntity.status(HttpStatus.OK).body(agent);
  }
}