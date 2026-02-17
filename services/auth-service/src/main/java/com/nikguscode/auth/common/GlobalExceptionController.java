package com.nikguscode.auth.common;

import com.nikguscode.auth.common.dto.ErrorCode;
import com.nikguscode.auth.common.dto.ErrorResponse;
import com.nikguscode.auth.auth.infrastructure.service.TokenErrorAnalyzer;
import jakarta.servlet.http.HttpServletRequest;
import java.time.OffsetDateTime;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.AuthenticationException;
import org.springframework.security.oauth2.jwt.JwtValidationException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

@RestControllerAdvice
@RequiredArgsConstructor
public class GlobalExceptionController {
  private final TokenErrorAnalyzer tokenErrorAnalyzer;

  @ExceptionHandler(AuthenticationException.class)
  public ResponseEntity<ErrorResponse> handleAuthenticationException(
      AuthenticationException ex, HttpServletRequest req) {
    ErrorResponse response = null;

    String authHeader = req.getHeader("Authorization");
    String token = (authHeader != null && authHeader.startsWith("Bearer "))
        ? authHeader.substring(7) : null;

    if (token == null) {
      ErrorCode errorCode = ErrorCode.ACCESS_TOKEN_INVALID;
      response = new ErrorResponse(errorCode, errorCode.getDescription());
    }

    if (ex.getCause() instanceof JwtValidationException) {
      response = tokenErrorAnalyzer.validate(token);
    }

    return (response != null) ?
        ResponseEntity.status(HttpStatus.UNAUTHORIZED).body(response)
        : ResponseEntity.status(HttpStatus.UNAUTHORIZED).body(assembleInternalErrorResponse());
  }

  private ErrorResponse assembleInternalErrorResponse() {
    ErrorCode errorCode = ErrorCode.INTERNAL_ERROR;
    return new ErrorResponse(errorCode, errorCode.getDescription());
  }
}