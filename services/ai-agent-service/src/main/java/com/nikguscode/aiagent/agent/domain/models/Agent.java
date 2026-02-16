package com.nikguscode.aiagent.agent.domain.models;

import java.util.UUID;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.RequiredArgsConstructor;
import lombok.ToString;

@RequiredArgsConstructor(access = AccessLevel.PRIVATE)
@Getter
@ToString
public class Agent {
  private final UUID id;
  private final String username;
  private final String photoLink;
  private final Boolean isMale;
  private final Integer age;

  @ToString.Exclude
  private final String interests;

  @ToString.Exclude
  private final String traits;

  @ToString.Exclude
  private final String additionalInformation;
}