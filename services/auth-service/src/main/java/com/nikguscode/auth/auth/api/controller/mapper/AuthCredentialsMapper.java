package com.nikguscode.auth.auth.api.controller.mapper;

import com.nikguscode.auth.auth.api.controller.dto.LoginDto;
import com.nikguscode.auth.auth.api.controller.dto.SignupDto;
import com.nikguscode.auth.auth.application.commands.UserSignInCommand;
import com.nikguscode.auth.user.application.commands.UserSignupCommand;
import org.mapstruct.Mapper;

@Mapper(componentModel = "spring")
public interface AuthCredentialsMapper {
  UserSignupCommand toSignupCommand(SignupDto dto);

  UserSignInCommand toSigninCommand(LoginDto dto);
}