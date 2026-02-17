package com.nikguscode.aiagentservice.aiagent.api.controller;

import com.nikguscode.aiagentservice.aiagent.api.dto.AgentCreateDto;
import com.nikguscode.aiagentservice.aiagent.api.dto.AgentUpdateDto;
import com.nikguscode.aiagentservice.aiagent.api.mapper.AiAgentWebMapper;
import com.nikguscode.aiagentservice.aiagent.application.AiAgentCommand;
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
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RequiredArgsConstructor
@RequestMapping("api/v1/ai-agent")
@RestController
public class AiAgentController {
  private final AiAgentWebMapper mapper;
  private final AiAgentUsecase aiAgentUsecase;

  @PostMapping("/agents")
  public ResponseEntity<Void> createAiAgent(@RequestBody @Validated AgentCreateDto dto) {
    AiAgentCommand command = mapper.toCommand(dto);
    aiAgentUsecase.registerAgent(command);
    return ResponseEntity.status(HttpStatus.CREATED).build();
  }

  @PutMapping("/agents/{agentId}")
  public ResponseEntity<Void> updateAiAgent(
      @PathVariable("agentId") UUID agentId, @RequestBody @Validated AgentUpdateDto dto) {
    AiAgentCommand command = mapper.toCommand(dto);
    aiAgentUsecase.updateAgent(command, agentId);
    return ResponseEntity.status(HttpStatus.NO_CONTENT).build();
  }

  @DeleteMapping("/agents/{agentId}")
  public ResponseEntity<Void> deleteAiAgent(@PathVariable("agentId") UUID agentId) {
    aiAgentUsecase.removeAgent(agentId);
    return ResponseEntity.status(HttpStatus.NO_CONTENT).build();
  }

  @GetMapping("/agents/{agentId}")
  public ResponseEntity<AiAgent> getAiAgent(@PathVariable("agentId") UUID agentId) {
    AiAgent agent = aiAgentUsecase.findAgent(agentId);
    return ResponseEntity.status(HttpStatus.OK).body(agent);
  }
}