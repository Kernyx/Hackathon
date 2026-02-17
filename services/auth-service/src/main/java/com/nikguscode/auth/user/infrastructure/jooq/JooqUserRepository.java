package com.nikguscode.auth.user.infrastructure.jooq;

import static com.nikguscode.auth.jooq.Tables.USER_SESSIONS;
import static com.nikguscode.auth.jooq.tables.User.USER;

import com.nikguscode.auth.auth.domain.UserSession;
import com.nikguscode.auth.jooq.tables.records.UserRecord;
import com.nikguscode.auth.jooq.tables.records.UserSessionsRecord;
import com.nikguscode.auth.user.domain.UserRepository;
import com.nikguscode.auth.user.domain.models.User;
import java.util.Optional;
import lombok.RequiredArgsConstructor;
import org.jooq.DSLContext;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.stereotype.Service;

@Service
@RequiredArgsConstructor
public class JooqUserRepository implements UserRepository {
  private final DSLContext dsl;

  @Override
  public void save(User user) {
    try {
      UserRecord userRecord = dsl.newRecord(USER, user);
      userRecord.store();
    } catch (DuplicateKeyException e) {
      throw new RuntimeException("Заглушка, на хакатоне заменить");
    }
  }

  @Override
  public Optional<User> findByEmail(String email) {
    return dsl
        .selectFrom(USER)
        .where(USER.EMAIL.eq(email))
        .fetchOptionalInto(User.class);
  }

  @Override
  public void rotateRefreshToken(UserSession userSession) {
    UserSessionsRecord record = dsl.newRecord(USER_SESSIONS, userSession);
    record.store();
  }
}