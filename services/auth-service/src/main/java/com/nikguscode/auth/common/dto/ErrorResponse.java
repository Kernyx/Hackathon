package com.nikguscode.auth.common.dto;

import java.time.OffsetDateTime;
import java.util.UUID;

public record ErrorResponse(
    ErrorCode code,
    String message,
    OffsetDateTime timestamp,
    UUID traceId
) {
  public ErrorResponse(ErrorCode code, String message) {
    this(code, message, OffsetDateTime.now(), UUID.randomUUID());
  }
}
