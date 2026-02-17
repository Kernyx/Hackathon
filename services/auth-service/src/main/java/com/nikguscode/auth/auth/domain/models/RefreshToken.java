package com.nikguscode.auth.auth.domain.models;

import com.nikguscode.auth.auth.domain.SessionDomainException;
import java.time.Instant;
import java.util.UUID;

public record RefreshToken(
    UUID token,
    Instant expirationDateTime
) {
  public RefreshToken {
    if (token == null || expirationDateTime == null) {
      throw new SessionDomainException("Token and expirationDateTime required fields");
    }
  }

  public static RefreshToken createToken(UUID token, Instant expirationDateTime) {
    return new RefreshToken(token, expirationDateTime);
  }
}