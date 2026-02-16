package com.nikguscode.aiagentservice.aiagent.application;

import com.nikguscode.aiagentservice.aiagent.domain.models.AiAgentTraits;
import com.nikguscode.aiagentservice.aiagent.domain.models.PersonalityType;
import java.util.UUID;

public record AiAgentCommand(
    UUID userId,
    String username,
    String photoLink,
    boolean isMale,
    Integer age,
    String interests,
    PersonalityType personalityType,
    AiAgentTraits traits,
    String additionalInformation
) {}