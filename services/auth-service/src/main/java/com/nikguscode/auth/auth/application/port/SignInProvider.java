package com.nikguscode.auth.auth.application.port;

import com.nikguscode.auth.auth.application.commands.UserSignInCommand;
import org.springframework.security.core.Authentication;

public interface SignInProvider {
  Authentication authenticate(UserSignInCommand command);
}