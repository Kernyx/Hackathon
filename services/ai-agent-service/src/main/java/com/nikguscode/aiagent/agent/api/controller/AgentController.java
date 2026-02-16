package com.nikguscode.aiagent.agent.api.controller;

import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RequestMapping("/api/v1/ai-agent")
@RestController
public class AgentController {
  @PostMapping("/ai-agents")
}