package com.nikguscode.auth.user.application.commands;

public record UserSignupCommand(
    String username,
    String email,
    String password
) {}