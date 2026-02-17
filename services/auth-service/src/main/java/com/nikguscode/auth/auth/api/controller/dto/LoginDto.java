package com.nikguscode.auth.auth.api.controller.dto;

public record LoginDto(
    String email,
    String password
) {}