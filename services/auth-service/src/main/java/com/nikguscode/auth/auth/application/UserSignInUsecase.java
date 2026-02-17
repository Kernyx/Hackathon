package com.nikguscode.auth.auth.application;

import com.nikguscode.auth.common.dto.ErrorCode;
import com.nikguscode.auth.common.dto.ErrorResponse;
import com.nikguscode.auth.auth.application.commands.UserSignInCommand;
import com.nikguscode.auth.auth.application.port.SignInProvider;
import com.nikguscode.auth.auth.application.port.TokenProvider;
import com.nikguscode.auth.auth.domain.MyAuthenticationException;
import com.nikguscode.auth.auth.domain.models.RefreshToken;
import com.nikguscode.auth.auth.domain.models.TokenPair;
import com.nikguscode.auth.user.domain.UserRepository;
import com.nikguscode.auth.user.domain.models.MyUserPrincipal;
import java.util.UUID;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.Authentication;
import org.springframework.stereotype.Service;

@Service
@RequiredArgsConstructor
public class UserSignInUsecase {
  private final SignInProvider signInProvider;
  private final TokenProvider tokenProvider;
  private final UserRepository userRepository;

  public TokenPair signin(UserSignInCommand command) {
    Authentication authentication = signInProvider.authenticate(command);

    String accessToken = tokenProvider.generateAccessToken(authentication);
    RefreshToken refreshToken = assignRefreshToken(authentication);

    return new TokenPair(accessToken, refreshToken);
  }

  private RefreshToken assignRefreshToken(Authentication authentication) {
    MyUserPrincipal userPrincipal = (MyUserPrincipal) authentication.getPrincipal();

    if (userPrincipal == null) {
      ErrorCode errorCode = ErrorCode.INTERNAL_ERROR;
      throw new MyAuthenticationException(
          new ErrorResponse(errorCode, errorCode.getDescription()));
    }

    UUID userId = userPrincipal.getId();
    return tokenProvider.rotateRefreshToken(userId);
  }
}