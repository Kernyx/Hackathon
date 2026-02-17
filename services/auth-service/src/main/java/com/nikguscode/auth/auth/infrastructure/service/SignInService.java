package com.nikguscode.auth.auth.infrastructure.service;

import com.nikguscode.auth.auth.application.commands.UserSignInCommand;
import com.nikguscode.auth.auth.application.port.SignInProvider;
import lombok.RequiredArgsConstructor;
import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.userdetails.UsernameNotFoundException;
import org.springframework.stereotype.Service;

@Service
@RequiredArgsConstructor
public class SignInService implements SignInProvider {
  private final AuthenticationManager authenticationManager;

  @Override
  public Authentication authenticate(UserSignInCommand command) {
    System.out.println(command);
    Authentication authentication =
        authenticationManager.authenticate(
            new UsernamePasswordAuthenticationToken(command.email(), command.password()));

    System.out.println("1");

    if (authentication.isAuthenticated()) {
      return authentication;
    }

    throw new UsernameNotFoundException(String.format("User:[%s] not found", command.email()));
  }
}