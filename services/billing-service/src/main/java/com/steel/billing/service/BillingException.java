package com.steel.billing.service;

import lombok.Getter;

@Getter
public class BillingException extends RuntimeException {
    private final String code;
    public BillingException(String code, String msg) { super(msg); this.code = code; }
}
