package com.nikguscode.aiagentservice.aiagent.domain.models;

import lombok.Getter;

@Getter
public enum PersonalityType {
  ALTRUIST("ALTRUIST"),
  MACHIAVELLIAN("MACHIAVELIIAN"),
  REBEL("REBEL"),
  STOIC("STOIC"),
  INDIVIDUAL("INDIVIDUAL");

  private final String value;

  PersonalityType(String value) {
    this.value = value;
  }
}