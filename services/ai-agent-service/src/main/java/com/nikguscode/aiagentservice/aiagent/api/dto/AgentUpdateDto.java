package com.nikguscode.aiagentservice.aiagent.api.dto;

import com.nikguscode.aiagentservice.aiagent.domain.models.AiAgentTraits;
import com.nikguscode.aiagentservice.aiagent.domain.models.PersonalityType;
import jakarta.validation.constraints.NotNull;
import java.util.UUID;

public record AgentUpdateDto(
    @NotNull(message = "User id can't be null")
    UUID userId,

    @NotNull(message = "Username is required field")
    String username,

    String photoLink,

    @NotNull(message = "Gender is required field")
    Boolean isMale,

    @NotNull(message = "Age is required field")
    Integer age,

    String interests,

    @NotNull(message = "Personality type is required field")
    PersonalityType personalityType,

    @NotNull(message = "Traits is required field")
    AiAgentTraits traits,
    String additionalInformation
) {}