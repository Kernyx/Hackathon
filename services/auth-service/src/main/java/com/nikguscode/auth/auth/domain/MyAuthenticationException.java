package com.nikguscode.auth.auth.domain;

import com.nikguscode.auth.common.dto.ErrorResponse;
import lombok.Getter;

@Getter
public class MyAuthenticationException extends RuntimeException {
  private final ErrorResponse errorResponse;

  public MyAuthenticationException(ErrorResponse errorResponse) {
    super();
    this.errorResponse = errorResponse;
  }
}