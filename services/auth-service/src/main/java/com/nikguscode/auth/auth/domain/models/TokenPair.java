package com.nikguscode.auth.auth.domain.models;

public record TokenPair(
    String accessToken,
    RefreshToken refreshToken
) {}
