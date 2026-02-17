package com.nikguscode.auth.auth.api.controller;

import com.nikguscode.auth.common.dto.SuccessResponse;
import com.nikguscode.auth.auth.api.controller.dto.LoginDto;
import com.nikguscode.auth.auth.api.controller.dto.SignupDto;
import com.nikguscode.auth.auth.api.controller.mapper.AuthCredentialsMapper;
import com.nikguscode.auth.auth.application.UserSignInUsecase;
import com.nikguscode.auth.auth.application.commands.UserSignInCommand;
import com.nikguscode.auth.auth.domain.models.TokenPair;
import com.nikguscode.auth.user.application.UserSignupUsecase;
import com.nikguscode.auth.user.application.commands.UserSignupCommand;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseCookie;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/auth")
@RequiredArgsConstructor
public class AuthController {
  private final AuthCredentialsMapper authCredentialsMapper;
  private final UserSignupUsecase userSignupUsecase;
  private final UserSignInUsecase userSignInUsecase;

  @PostMapping("/signup")
  public ResponseEntity<Void> signup(@RequestBody @Validated SignupDto dto) {
    UserSignupCommand command = authCredentialsMapper.toSignupCommand(dto);
    userSignupUsecase.signup(command);
    return ResponseEntity.status(HttpStatus.CREATED).build();
  }

  @PostMapping("/signin")
  public ResponseEntity<SuccessResponse<String>> signin(@RequestBody @Validated LoginDto dto) {
    UserSignInCommand command = authCredentialsMapper.toSigninCommand(dto);
    TokenPair tokenPair = userSignInUsecase.signin(command);
    ResponseCookie refreshTokenCookie = assembleCookie(tokenPair);

    return ResponseEntity.ok()
        .header(HttpHeaders.SET_COOKIE, refreshTokenCookie.toString())
        .body(SuccessResponse.ok(tokenPair.accessToken()));
  }

//  @PostMapping("/refresh-token")
//  public ResponseEntity<SuccessResponse<String>> refreshToken(HttpServletRequest req) {
//
//  }

  private ResponseCookie assembleCookie(TokenPair tokenPair) {
    String refreshToken = tokenPair.refreshToken().token().toString();
    Long secondsUntilExpiration = calculateSecondsUntilCookieExpiration(tokenPair);

    return ResponseCookie
        .from("refreshToken", refreshToken)
        .httpOnly(true)
        .path("/")
        .maxAge(secondsUntilExpiration)
        .build();
  }

  private Long calculateSecondsUntilCookieExpiration(TokenPair tokenPair) {
    Instant now = Instant.now();
    Instant exp = tokenPair.refreshToken().expirationDateTime();
    return ChronoUnit.SECONDS.between(now, exp);
  }
}