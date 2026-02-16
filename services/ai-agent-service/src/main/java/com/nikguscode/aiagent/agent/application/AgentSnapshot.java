package com.nikguscode.aiagent.agent.application;

import com.nikguscode.aiagent.api.model.PersonalityType;

public record AgentSnapshot(
    String username,
    String photoLink,
    boolean isMale,
    Integer age,
    String interests,
    PersonalityType personalityType,
    String traits,
    String additionalInformation
) {}