package com.nikguscode.auth.user.domain;

import com.nikguscode.auth.auth.domain.UserSession;
import com.nikguscode.auth.auth.domain.models.RefreshToken;
import com.nikguscode.auth.user.domain.models.User;
import java.util.Optional;
import java.util.UUID;

public interface UserRepository {
  void save(User user);

  Optional<User> findByEmail(String login);

  void rotateRefreshToken(UserSession userSession);
}