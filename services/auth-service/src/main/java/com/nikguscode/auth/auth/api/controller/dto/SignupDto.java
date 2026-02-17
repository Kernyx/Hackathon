package com.nikguscode.auth.auth.api.controller.dto;

public record SignupDto(
    String username,
    String email,
    String password
) {}