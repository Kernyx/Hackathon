package com.nikguscode.auth.auth.application.commands;

public record UserSignInCommand(
    String email,
    String password
) {}