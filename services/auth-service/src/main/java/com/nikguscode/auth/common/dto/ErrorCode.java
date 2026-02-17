package com.nikguscode.auth.common.dto;

import com.fasterxml.jackson.annotation.JsonValue;
import lombok.Getter;
import lombok.RequiredArgsConstructor;

@Getter
@RequiredArgsConstructor
public enum ErrorCode {
  INTERNAL_ERROR("A-1000", "Internal error"),

  INVALID_SIGNUP_CREDENTIALS("A-S1001", "Invalid signup credentials"),

  INVALID_LOGIN_CREDENTIALS("A-L1001", "Invalid login credentials"),
  ACCOUNT_BANNED("A-L1002", "Account banned"),
  TOO_MANY_LOGIN_ATTEMPTS("A-L1003", "Too many login attempts"),

  ACCESS_TOKEN_EXPIRED("A-AT1001", "Access token expired"),
  ACCESS_TOKEN_INVALID("A-AT1002", "Access token signature invalid"),

  REFRESH_TOKEN_EXPIRED("A-RT1001", "Refresh token expired"),
  REFRESH_TOKEN_INVALID("A-RT1002", "Refresh token invalid"),

  INSUFFICIENT_PERMISSIONS("A-R1001", "Insufficient permissions"),
  FORBIDDEN_RESOURCE("A-R1002", "Forbidden resource"),
  ROLE_NOT_ALLOWED("A-R1003", "Role not allowed");

  private final String value;
  private final String description;

  @JsonValue
  public String getValue() {
    return value;
  }
}