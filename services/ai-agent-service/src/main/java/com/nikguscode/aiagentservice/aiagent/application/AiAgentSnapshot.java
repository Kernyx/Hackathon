package com.nikguscode.aiagentservice.aiagent.application;

import com.nikguscode.aiagentservice.aiagent.domain.models.AiAgentTraits;
import com.nikguscode.aiagentservice.aiagent.domain.models.PersonalityType;

public record AiAgentSnapshot(
    String username,
    String photoLink,
    boolean isMale,
    Integer age,
    String interests,
    PersonalityType personalityType,
    AiAgentTraits traits,
    String additionalInformation
) {}