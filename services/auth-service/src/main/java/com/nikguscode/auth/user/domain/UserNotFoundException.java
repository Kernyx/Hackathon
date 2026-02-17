package com.nikguscode.auth.user.domain;

import lombok.Getter;

@Getter
public class UserNotFoundException extends RuntimeException {
  private final String responseMessage;

  public UserNotFoundException(String responseMessage) {
    super();
    this.responseMessage = responseMessage;
  }
}