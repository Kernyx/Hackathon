package com.nikguscode.auth.common.dto;

import com.fasterxml.jackson.annotation.JsonPropertyOrder;

@JsonPropertyOrder({"status", "httpCode", "data"})
public record SuccessResponse<T>(
    String status,
    Integer httpCode,
    T data
) {
  public static <T> SuccessResponse<T> ok(T data) {
    return new SuccessResponse<>("Success", 200, data);
  }
}