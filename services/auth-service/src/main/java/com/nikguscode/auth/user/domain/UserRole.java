package com.nikguscode.auth.user.domain;

import lombok.Getter;

@Getter
public enum UserRole {
  USER("USER"),
  MODERATOR("MODERATOR"),
  ADMIN("ADMIN"),
  UNDEFINED("UNDEFINED");

  private final String value;

  UserRole(String value) {
    this.value = value;
  }
}