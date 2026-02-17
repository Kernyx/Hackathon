package com.nikguscode.auth.auth.domain;

import java.time.OffsetDateTime;
import java.util.UUID;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.RequiredArgsConstructor;

@RequiredArgsConstructor(access = AccessLevel.PRIVATE)
@Getter
public class UserSession {
  private static final Long EXPIRE_OFFSET_IN_HOURS = 6L;

  private final UUID id;
  private final UUID userId;
  private final String refreshTokenHash;
  private final OffsetDateTime expiresAt;
  private final String ipAddress;
  private final String userAgent;
  private final String deviceInfo;
  private final OffsetDateTime createdAt;

  public static UserSession createSession(
      UUID userId, String refreshTokenHash, String ipAddress, String userAgent, String deviceInfo) {
    validate(userId, refreshTokenHash);
    return new UserSession(
        UUID.randomUUID(), userId, refreshTokenHash, calculateExpireDateTime(),
        ipAddress, userAgent, deviceInfo, OffsetDateTime.now());
  }

  private static OffsetDateTime calculateExpireDateTime() {
    OffsetDateTime now = OffsetDateTime.now();
    return now.plusHours(EXPIRE_OFFSET_IN_HOURS);
  }

  private static void validate(UUID userId, String refreshTokenHash) {
    if (userId == null) {
      throw new SessionDomainException("userId didn't pass validation");
    }

    if (refreshTokenHash == null || refreshTokenHash.length() < 10) {
      throw new SessionDomainException("refreshTokenHash didn't pass validation");
    }
  }
}