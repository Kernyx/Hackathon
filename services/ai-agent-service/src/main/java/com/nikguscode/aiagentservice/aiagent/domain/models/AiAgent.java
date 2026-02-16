package com.nikguscode.aiagentservice.aiagent.domain.models;

import com.nikguscode.aiagentservice.aiagent.application.AiAgentSnapshot;
import java.util.UUID;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.RequiredArgsConstructor;
import lombok.ToString;

@RequiredArgsConstructor(access = AccessLevel.PRIVATE)
@Getter
@ToString
public class AiAgent {
  private final UUID id;
  private final String username;
  private final String photoLink;
  private final Boolean isMale;
  private final Integer age;

  @ToString.Exclude
  private final String interests;

  private final PersonalityType personalityType;

  @ToString.Exclude
  private final AiAgentTraits traits;

  @ToString.Exclude
  private final String additionalInformation;

  public static AiAgent createAgent(AiAgentSnapshot snapshot) {
    return new AiAgent(
        UUID.randomUUID(), snapshot.username(), snapshot.photoLink(), snapshot.isMale(),
        snapshot.age(), snapshot.interests(), snapshot.personalityType(), snapshot.traits(),
        snapshot.additionalInformation());
  }

  public static AiAgent restore(
      UUID id, String username, String photoLink, boolean isMale, Integer age, String interests,
      PersonalityType personalityType, AiAgentTraits traits, String additionalInformation) {
    return new AiAgent(
        id, username, photoLink, isMale, age, interests,
        personalityType, traits, additionalInformation);
  }
}