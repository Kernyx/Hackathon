package com.nikguscode.auth.auth.application.port;

import com.nikguscode.auth.auth.domain.models.RefreshToken;
import java.util.UUID;
import org.springframework.security.core.Authentication;

public interface TokenProvider {
  String generateAccessToken(Authentication authentication);

  RefreshToken rotateRefreshToken(UUID userId);
}