package com.nikguscode.aiagentservice.aiagent.api.controller;

import com.nikguscode.aiagentservice.aiagent.application.AiAgentUsecase;
import com.nikguscode.aiagentservice.aiagent.domain.models.AiAgent;
import java.util.List;
import java.util.UUID;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RequiredArgsConstructor
@RequestMapping("api/v1/ai-agent")
@RestController
public class UserController {
  private final AiAgentUsecase aiAgentUsecase;

  @GetMapping("users/{userId}/agents")
  public List<AiAgent> getUserAgents(@PathVariable("userId") UUID userId) {
    return aiAgentUsecase.findAgentsByUserId(userId);
  }
}