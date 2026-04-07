class RiskCalculator:
    def __init__(self, fee_rate=0.0004):
        """
        Initializes the Risk Calculator. 
        fee_rate defaults to 0.04% (Taker fee on Binance Futures roughly).
        """
        self.fee_rate = fee_rate

    def calculate_pre_flight_risk(self, order_data, account_equity, mark_price):
        """
        Calculates expected PnL and risk percentages before order execution.
        Returns a dictionary matching the Pre-Flight Data Schema.
        """
        # Note: This is a simplified calculation for standard contracts
        # In actual production, it must account for exact lot sizes and multiplier
        
        symbol = order_data.get('symbol', 'BTCUSDT')
        side = order_data.get('side', 'BUY')
        size_type = order_data.get('size_type', 'USDT')
        size_value = order_data.get('size_value', 0.0)
        tp_sl_type = order_data.get('tp_sl_type', 'PRICE')
        tp_value = order_data.get('tp_value', 0.0)
        sl_value = order_data.get('sl_value', 0.0)
        
        if size_type == 'ASSET':
            quantity_asset = size_value
            position_size_usdt = quantity_asset * mark_price
        else:
            position_size_usdt = size_value
            quantity_asset = position_size_usdt / mark_price if mark_price > 0 else 0

        if tp_sl_type == 'PNL' and quantity_asset > 0:
            target_tp_pnl = tp_value
            target_sl_pnl = sl_value
            
            if side == 'BUY':
                tp_price = mark_price + (target_tp_pnl / quantity_asset) if target_tp_pnl > 0 else 0
                sl_price = mark_price - (target_sl_pnl / quantity_asset) if target_sl_pnl > 0 else 0
            else: # SELL
                tp_price = mark_price - (target_tp_pnl / quantity_asset) if target_tp_pnl > 0 else 0
                sl_price = mark_price + (target_sl_pnl / quantity_asset) if target_sl_pnl > 0 else 0
                
            tp_value = max(0, tp_price)
            sl_value = max(0, sl_price)
            # Update order_data so converted values can be used downstream if needed
            order_data['tp_value'] = round(tp_value, 2)
            order_data['sl_value'] = round(sl_value, 2)

        # Test 5: Inverted Execution Logic (Spread Violation)
        if side == 'BUY':
            if tp_value > 0 and tp_value <= mark_price:
                return {"valid_for_execution": False, "rejection_reason": "Invalid TP: Take Profit for a LONG position must be strictly above the entry price."}
            if sl_value > 0 and sl_value >= mark_price:
                return {"valid_for_execution": False, "rejection_reason": "Invalid SL: Stop Loss for a LONG position must be strictly below the entry price."}
        elif side == 'SELL':
            if tp_value > 0 and tp_value >= mark_price:
                return {"valid_for_execution": False, "rejection_reason": "Invalid TP: Take Profit for a SHORT position must be strictly below the entry price."}
            if sl_value > 0 and sl_value <= mark_price:
                return {"valid_for_execution": False, "rejection_reason": "Invalid SL: Stop Loss for a SHORT position must be strictly above the entry price."}

        # Test 2: Minimum Notional Check
        if position_size_usdt < 5.0:
            return {"valid_for_execution": False, "rejection_reason": "Execution BLOCKED: Minimum notional value for Binance Futures is 5 USDT."}

        # Fees on entry and exit (approximate based on position size)
        order_type_str = order_data.get('order_type', 'MARKET').upper()
        # Enforcing worst-case Taker rate (self.fee_rate) to maintain safe margin validty threshold
        entry_fee_rate = self.fee_rate
        exit_fee_rate = self.fee_rate # Assuming conditional exit (TAKE_PROFIT_MARKET / STOP_MARKET)
        estimated_trading_fees = (position_size_usdt * entry_fee_rate) + (position_size_usdt * exit_fee_rate)

        # Potential PnL based on TP and SL
        target_pnl = 0.0
        risk_pnl = 0.0
        
        if side == 'BUY':
            if tp_value > mark_price:
                target_pnl = (tp_value - mark_price) * quantity_asset
            if sl_value > 0 and sl_value < mark_price:
                risk_pnl = (mark_price - sl_value) * quantity_asset
        elif side == 'SELL':
            if tp_value > 0 and tp_value < mark_price:
                target_pnl = (mark_price - tp_value) * quantity_asset
            if sl_value > mark_price:
                risk_pnl = (sl_value - mark_price) * quantity_asset

        net_pnl_expected = target_pnl - estimated_trading_fees
        net_risk_exposure = risk_pnl + estimated_trading_fees
        net_loss_expected = -net_risk_exposure

        # Calculate equity at stake
        risk_pct_equity_at_stake = (net_risk_exposure / account_equity * 100) if account_equity > 0 else 100.0

        # Arbitrary safety limits for now (e.g. max 5% loss per trade)
        valid_for_execution = True
        reason = ""
        
        # Test 3: Margin Exhaustion & Fee Collision
        leverage = order_data.get('leverage', 20)
        margin_required = position_size_usdt / leverage
        if margin_required + estimated_trading_fees > account_equity:
            valid_for_execution = False
            reason = f"Margin Exhaustion: (Margin {round(margin_required, 2)} + Fees {round(estimated_trading_fees, 2)}) exceeds available balance {account_equity}."
            
        if risk_pct_equity_at_stake > 5.0 and valid_for_execution:
            valid_for_execution = False
            reason = "Risk exceeds 5% of account equity"
            
        if net_risk_exposure > account_equity and valid_for_execution:
            valid_for_execution = False
            reason = "Risk exceeds total account equity"

        return {
            "gross_pnl_target": round(target_pnl, 2),
            "estimated_trading_fees": round(estimated_trading_fees, 2),
            "net_pnl_expected": round(net_pnl_expected, 2),
            "net_loss_expected": round(net_loss_expected, 2),
            "risk_pct_equity_at_stake": round(risk_pct_equity_at_stake, 2),
            "valid_for_execution": valid_for_execution,
            "rejection_reason": reason
        }
