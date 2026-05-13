package com.steel.billing.model;

import lombok.Data;

@Data
public class Wallet {
    private Long tenantId;
    private Long tokenBalance;
    private Integer timesBalance;
    private Long subQuota;
    private Long subUsed;
    private Long subPeriodLeft;        // 派生 = subQuota - subUsed
    private Integer overrunLimitCent;
    private Integer overrunUsedCent;
    private Integer overrunPriceCentPer1k;
    private Long version;
}
