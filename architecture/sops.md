# Terminal Trading SOPs

## 1. Execution Flow
1. **Startup & Auth:** The user launches the CLI (`python -m cli.main`). The CLI immediately prompts for a local passphrase to authenticate the developer.
2. **Environment Load:** Load `.env`. Ensure Binance API keys (Testnet or Prod based on config) are loaded correctly.
3. **Interactive Collection:** 
   * Pre-fill common defaults if applicable (e.g., Symbol: BTCUSDT).
   * Ask for Order Type, Side, Size Type (USDT/Asset), Size Value, TP/SL points.
4. **Pre-Flight Validation:**
   * Risk Calculator computes gross PnL, fees, and net PnL.
   * Compares risk % against Account Equity.
   * Halts if Target PnL leads to equity ruin.
5. **Confirmation:**
   * A Rich Table displays the pre-flight calculations.
   * User must hit ENTER to confirm execution.
6. **Execution & Logging:**
   * Order strings are converted into Binance API params.
   * HTTP requests executed via Binance Client.
   * Trade response logged in `progress.md` and Terminal.

## 2. Risk Constraints
* **Max Risk per Trade:** (Developer defined, e.g., 2% of equity). If `risk_pct_equity_at_stake` over limits, reject.
* **Leverage Validation:** Leverage is visually confirmed before order string reaches the API.

## 3. Error Handling
* **API Disconnect:** If connection times out, gracefully exit with context; do not silently fail.
* **Insufficient Funds:** Catch Binance error code or block locally via pre-flight prior to API request.
