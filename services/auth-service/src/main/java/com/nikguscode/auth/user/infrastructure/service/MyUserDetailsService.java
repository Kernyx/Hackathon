package com.nikguscode.auth.user.infrastructure.service;

import com.nikguscode.auth.user.domain.UserRepository;
import com.nikguscode.auth.user.domain.models.MyUserPrincipal;
import com.nikguscode.auth.user.domain.models.User;
import java.util.Optional;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.security.core.userdetails.UserDetailsService;
import org.springframework.security.core.userdetails.UsernameNotFoundException;
import org.springframework.stereotype.Service;

@Service
@RequiredArgsConstructor
public class MyUserDetailsService implements UserDetailsService {
  private final UserRepository userRepository;

  @Override
  public UserDetails loadUserByUsername(String email) throws UsernameNotFoundException {
    Optional<User> userOpt = userRepository.findByEmail(email);

    if (userOpt.isEmpty()) {
      throw new UsernameNotFoundException(String.format("User:[%s] not found", email));
    }

    return new MyUserPrincipal(userOpt.get());
  }
}
