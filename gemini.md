# Project Constitution

## 1. Data Schema definition (Input / Output Shapes)
**Status:** Defined (Awaiting Approval)

### Order Request Schema (Input)
```json
{
  "symbol": "BTCUSDT",
  "order_type": "MARKET", // Also supports LIMIT, STOP_MARKET, TAKE_PROFIT_MARKET
  "side": "BUY", // BUY or SELL
  "leverage_confirmed": true,
  "size_type": "USDT", // USDT or ASSET
  "size_value": 150.0,
  "tp_sl_type": "PRICE", // PRICE or PNL
  "tp_value": 72000.0,
  "sl_value": 64000.0
}
```

### Pre-Flight Data Schema (Hypothetical Calculation)
```json
{
  "gross_pnl_target": 25.0,
  "estimated_trading_fees": 1.25,
  "net_pnl_expected": 23.75,
  "risk_pct_equity_at_stake": 2.5,
  "valid_for_execution": true
}
```

### Order Output Schema (Output)
```json
{
  "status": "SUCCESS",
  "order_id": 123456789,
  "client_order_id": "testnet_12345",
  "executed_qty": 0.002,
  "avg_price": 68000.0
}
```

### Validation Logic
* If the hypothetical PnL exceeds the available balance, flag `valid_for_execution` as false and block execution.
* If price parameters are invalid for the order book (e.g., tick size mismatch or SL on wrong side of price), block execution and return explicit error message.
* If `leverage_confirmed` is false, block execution.

## 2. Behavioral Rules & Tone
* **Deterministic Safety:** No order is fired without explicit manual user validation. User must hit "Enter" after final review.
* **Professional Logic:** Natively handle specific advanced types like `STOP_MARKET` and `TAKE_PROFIT_MARKET`.
* **Error States:** Display clear, blocking errors for insufficient balance or invalid order parameters, preventing any exchange rejection.

## 3. Architectural Invariants
* **Zero-Trust & Validation:** The terminal MUST print a breakdown of expected outcomes (theoretical PnL, risk %) prior to confirmation.
* **Isolation:** Environment mode toggle (Testnet vs Production). Default to Testnet. Keys loaded from `.env`.
* **Security:** Local authentication (username/password) required upon CLI startup, restricting access to primary developer only.
* **State Management:** Log every `orderId` and `clientOrderId` in `progress.md`.

## 4. Maintenance & Rollback Plan
*(To be populated in Phase 5: Trigger)*

## 5. Context Handoffs
*(Add a 1-3 line context handoff here after any meaningful task)*
