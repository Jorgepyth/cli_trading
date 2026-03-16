import unittest
from tools.risk_calculator import RiskCalculator

class TestRiskCalculator(unittest.TestCase):
    def setUp(self):
        self.calc = RiskCalculator(fee_rate=0.0004) # 0.04%

    def test_buy_order_risk(self):
        order_data = {
            'symbol': 'BTCUSDT',
            'side': 'BUY',
            'size_value': 1000.0, # 1000 USDT position
            'tp_value': 70000.0,
            'sl_value': 60000.0
        }
        account_equity = 100.0
        mark_price = 65000.0

        result = self.calc.calculate_pre_flight_risk(order_data, account_equity, mark_price)

        # Quantity = 1000 / 65000 = 0.01538...
        # Gross PnL Target = (70000 - 65000) * 0.01538... = 5000 * 0.01538... = 76.92
        # Risk PnL = (65000 - 60000) * 0.01538... = 5000 * 0.01538... = 76.92
        # Fees = (1000 * 0.0004) * 2 = 0.8
        # Net Expected PnL = 76.92 - 0.8 = 76.12
        # Net Risk Exposure = 76.92 + 0.8 = 77.72
        # Risk % = (77.72 / 100) * 100 = 77.72%
        
        # We expect validation to fail because Risk % > 5%
        self.assertFalse(result['valid_for_execution'])
        self.assertAlmostEqual(result['gross_pnl_target'], 76.92, places=2)
        self.assertAlmostEqual(result['estimated_trading_fees'], 0.8)
        self.assertAlmostEqual(result['net_pnl_expected'], 76.12, places=2)

    def test_sell_order_risk_safe(self):
        order_data = {
            'symbol': 'BTCUSDT',
            'side': 'SELL',
            'size_value': 200.0,
            'tp_value': 60000.0,
            'sl_value': 66000.0
        }
        account_equity = 400.0  # Safe account
        mark_price = 65000.0
        
        result = self.calc.calculate_pre_flight_risk(order_data, account_equity, mark_price)
        
        # Asset Qty = 200 / 65000 = 0.003076...
        # Risk PnL = (66000 - 65000) * 0.003076... = 1000 * 0.003076... = 3.076...
        # Fees = (200 * 0.0004) * 2 = 0.16
        # Total Expo = 3.23...
        # Risk % = (3.23... / 400) * 100 = 0.8... %
        
        self.assertTrue(result['valid_for_execution'])
        self.assertLess(result['risk_pct_equity_at_stake'], 5.0)

if __name__ == '__main__':
    unittest.main()
