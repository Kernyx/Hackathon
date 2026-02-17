package com.nikguscode.auth.auth.infrastructure.service;

import com.nikguscode.auth.common.dto.ErrorCode;
import com.nikguscode.auth.common.dto.ErrorResponse;
import com.nimbusds.jwt.SignedJWT;
import java.text.ParseException;
import java.time.Instant;
import java.time.OffsetDateTime;
import java.util.Date;
import org.springframework.stereotype.Service;

@Service
public class TokenErrorAnalyzer {
  public ErrorResponse validate(String token) {
    try {
      SignedJWT signedJWT = SignedJWT.parse(token);
      Date exp = signedJWT.getJWTClaimsSet().getExpirationTime();

      if (isExpired(exp)) {
        return assembleErrorResponse(ErrorCode.ACCESS_TOKEN_EXPIRED);
      }
    } catch (ParseException e) {
      return assembleErrorResponse(ErrorCode.ACCESS_TOKEN_INVALID);
    }

    return assembleErrorResponse(ErrorCode.INTERNAL_ERROR);
  }

  private boolean isExpired(Date exp) {
    return exp == null || exp.toInstant().isBefore(Instant.now());
  }

  private ErrorResponse assembleErrorResponse(ErrorCode errorCode) {
    return new ErrorResponse(errorCode, errorCode.getDescription());
  }
}