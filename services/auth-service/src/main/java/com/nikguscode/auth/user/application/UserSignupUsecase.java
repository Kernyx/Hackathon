package com.nikguscode.auth.user.application;

import com.nikguscode.auth.user.application.commands.UserSignupCommand;
import com.nikguscode.auth.user.domain.UserRepository;
import com.nikguscode.auth.user.domain.models.User;
import lombok.RequiredArgsConstructor;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
public class UserSignupUsecase {
  private final UserRepository userRepository;
  private final PasswordEncoder passwordEncoder;

  @Transactional
  public void signup(UserSignupCommand command) {
    String encodedPassword = passwordEncoder.encode(command.password());
    User user = User.registerUser(command.username(), command.email(), encodedPassword);
    userRepository.save(user);
  }
}