package com.nikguscode.auth.auth.infrastructure.service;

import com.nikguscode.auth.auth.application.port.TokenProvider;
import com.nikguscode.auth.auth.domain.MyAuthenticationException;
import com.nikguscode.auth.auth.domain.UserSession;
import com.nikguscode.auth.auth.domain.models.RefreshToken;
import com.nikguscode.auth.common.dto.ErrorCode;
import com.nikguscode.auth.common.dto.ErrorResponse;
import com.nikguscode.auth.user.domain.UserRepository;
import com.nikguscode.auth.user.domain.models.MyUserPrincipal;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.UUID;
import java.util.stream.Collectors;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.oauth2.jwt.JwtClaimsSet;
import org.springframework.security.oauth2.jwt.JwtEncoder;
import org.springframework.security.oauth2.jwt.JwtEncoderParameters;
import org.springframework.stereotype.Service;

@Service
@RequiredArgsConstructor
public class TokenService implements TokenProvider {
  private static final String issuer = "self";
  private static final Long accessTokenExpiration = 1L;
  private static final Long refreshTokenExpiration = 2L;

  private final JwtEncoder encoder;
  private final UserRepository userRepository;

  @Override
  public RefreshToken rotateRefreshToken(UUID userId) {
    RefreshToken refreshToken = generateRefreshToken();
    UserSession userSession = UserSession.createSession(userId, refreshToken.token().toString(), "",
        "", "");
    userRepository.rotateRefreshToken(userSession);
    return refreshToken;
  }

  @Override
  public String generateAccessToken(Authentication authentication) {
    Instant now = Instant.now();
    MyUserPrincipal myUserPrincipal = (MyUserPrincipal) authentication.getPrincipal();

    if (myUserPrincipal == null) {
      ErrorCode errorCode = ErrorCode.INTERNAL_ERROR;
      throw new MyAuthenticationException(new ErrorResponse(errorCode, errorCode.getDescription()));
    }

    UUID userId = myUserPrincipal.getId();

    String scope = authentication.getAuthorities().stream()
        .map(GrantedAuthority::getAuthority)
        .collect(Collectors.joining(" "));

    JwtClaimsSet claims = JwtClaimsSet.builder()
        .issuer("self")
        .issuedAt(now)
        .expiresAt(now.plus(accessTokenExpiration, ChronoUnit.DAYS))
        .subject(userId.toString())
        .claim("scope", scope)
        .build();

    return this.encoder.encode(JwtEncoderParameters.from(claims)).getTokenValue();
  }

  private RefreshToken generateRefreshToken() {
    Instant now = Instant.now();
    UUID refreshToken = UUID.randomUUID();

    return RefreshToken.createToken(
        refreshToken, now.plus(2, ChronoUnit.HOURS));
  }
}