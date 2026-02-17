package com.nikguscode.auth.user.domain.models;

import com.nikguscode.auth.user.domain.UserRole;
import java.beans.ConstructorProperties;
import java.time.OffsetDateTime;
import java.util.UUID;
import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.ToString;

@Getter
@ToString
public class User {
  private final UUID id;
  private final String username;
  private final String email;

  @ToString.Exclude
  private final String passwordHash;
  private final UserRole role;
  private final OffsetDateTime createdAt;

  @ConstructorProperties({"id", "username", "email", "password_hash", "role", "created_at"})
  public User(
      UUID id, String username, String email, String passwordHash,
      UserRole role, OffsetDateTime createdAt) {
    this.id = id;
    this.username = username;
    this.email = email;
    this.passwordHash = passwordHash;
    this.role = role;
    this.createdAt = createdAt;
  }

  public static User registerUser(String username, String email, String encodedPassword) {
    return new User(
        UUID.randomUUID(), username, email, encodedPassword, UserRole.USER, OffsetDateTime.now());
  }

  private void validate() {

  }

//  public User assignRefreshToken(RefreshToken refreshToken) {
//    return new User(
//        this.id, this.username, this.passwordHash, this.role,
//        refreshToken.token(), refreshToken.expirationDateTime());
//  }
}