package com.nikguscode.auth.auth.application;

import com.nikguscode.auth.auth.domain.models.TokenPair;
import java.util.UUID;
import org.springframework.stereotype.Service;

@Service
public class TokenUsecase {
  public TokenPair refreshAccessToken(UUID refreshToken) {
    return null;
  }
}
