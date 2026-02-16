package com.nikguscode.aiagent.agent.api.dto;

import com.nikguscode.aiagent.api.model.PersonalityType;
import jakarta.validation.constraints.NotNull;

public record AgentCreateDto(
    @NotNull
    String username,

    String photoLink,
    boolean isMale,

    @NotNull
    Integer age,

    String interests,

    @NotNull
    PersonalityType personalityType,

    @NotNull
    String traits,
    String additionalInformation
) {}