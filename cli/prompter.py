import click
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.console import Console
import rich.box

console = Console()

class InteractivePrompter:
    @staticmethod
    def collect_order_details(trading_client=None):
        """
        Interactive flow to gather order schema details.
        Matches the Order Request Schema from Protocol 0.
        """
        order_data = {}
        
        # Change 1: Show supported symbol options
        console.print("\n[bold]Available Symbols:[/bold] BTCUSDT, XAUUSDT")
        order_data['symbol'] = Prompt.ask("Symbol", choices=["BTCUSDT", "XAUUSDT"], default="BTCUSDT").upper()
        order_data['order_type'] = Prompt.ask("Order Type", choices=["MARKET", "LIMIT"], default="MARKET").upper()
        order_data['side'] = Prompt.ask("Side", choices=["BUY", "SELL"], default="BUY").upper()
        
        # Ask for limit price if LIMIT order is selected
        if order_data['order_type'] == 'LIMIT':
            console.print("[bold #aaaaaa]LIMIT order selected — you must specify the exact price at which to fill.[/bold #aaaaaa]")
            order_data['limit_price'] = float(Prompt.ask("Limit Price (USDT)"))
        else:
            order_data['limit_price'] = None
        
        # Change 2: Fetch and display current leverage before asking for confirmation
        if trading_client:
            console.print("\n[bold #aaaaaa]Fetching current leverage and margin mode from exchange...[/bold #aaaaaa]")
            current_leverage = trading_client.get_leverage(order_data['symbol'])
            margin_type = trading_client.get_margin_type(order_data['symbol'])
            
            if current_leverage and margin_type:
                console.print(f"  Current setup for [#00aaff]{order_data['symbol']}[/#00aaff]: [bold #aaaaaa]{margin_type} {current_leverage}x[/bold #aaaaaa]")
            elif current_leverage:
                console.print(f"  Current leverage for [#00aaff]{order_data['symbol']}[/#00aaff]: [bold #aaaaaa]{current_leverage}x[/bold #aaaaaa]")
            else:
                console.print("  [#aaaaaa]Could not fetch current leverage/margin.[/#aaaaaa]")
        order_data['leverage_confirmed'] = Confirm.ask("Is your setup (Leverage & Margin Mode) already set correctly on the exchange?")
        
        if not order_data['leverage_confirmed']:
             console.print("[bold #ffffff on #ff0000]Please set your leverage manually on the exchange first.[/bold #ffffff on #ff0000]")
             raise SystemExit()

        order_data['size_type'] = Prompt.ask("Size Type", choices=["USDT", "ASSET"], default="USDT").upper()
        order_data['size_value'] = float(Prompt.ask("Size Value"))
        
        # Change 3: Show all TP/SL type options (PRICE and PNL)
        console.print("\n[bold]TP/SL Types:[/bold]")
        console.print("  [#00aaff]PRICE[/#00aaff] - Set Take Profit and Stop Loss as exact price levels")
        console.print("  [#00aaff]PNL[/#00aaff]   - Set Take Profit and Stop Loss as target PnL amounts in USDT")
        order_data['tp_sl_type'] = Prompt.ask("Take-Profit / Stop-Loss Type", choices=["PRICE", "PNL"], default="PRICE").upper()
        
        if order_data['tp_sl_type'] == 'PRICE':
            order_data['tp_value'] = float(Prompt.ask("Take Profit Price", default="0.0"))
            order_data['sl_value'] = float(Prompt.ask("Stop Loss Price", default="0.0"))
        else:  # PNL
            order_data['tp_value'] = float(Prompt.ask("Take Profit Target (USDT PnL)", default="0.0"))
            order_data['sl_value'] = float(Prompt.ask("Stop Loss Limit (USDT PnL)", default="0.0"))
        
        return order_data
        
    @staticmethod
    def display_status_dashboard(client):
        """Fetches and displays account balance and open positions."""
        balance = client.get_account_balance()
        positions = client.get_open_positions()
        orders = client.get_open_orders()
        
        console.print(f"\n[bold #00aaff]Account Balance:[/bold #00aaff] {balance:.2f} USDT\n")
        
        if not positions:
            console.print("[#aaaaaa]No open positions found.[/#aaaaaa]")
        else:
            table = Table(
                title="Open Positions", 
                style="#00aaff", 
                box=rich.box.ROUNDED, 
                row_styles=["none", "dim"]
            )
            table.add_column("Symbol", style="#aaaaaa", no_wrap=True, justify="left")
            table.add_column("Size", style="#aaaaaa", justify="right")
            table.add_column("Entry Price", style="#aaaaaa", justify="right")
            table.add_column("Mark Price", style="#aaaaaa", justify="right")
            table.add_column("Margin/Leverage", style="#aaaaaa", justify="left")
            table.add_column("Unrealized PnL", justify="right")
            
            for pos in positions:
                pnl = pos['unRealizedProfit']
                pnl_color = "#00ff00" if pnl > 0 else "#ff0055" if pnl < 0 else "#aaaaaa"
                size_color = "#00ff00" if pos['amount'] > 0 else "#ff0055" if pos['amount'] < 0 else "#aaaaaa"
                table.add_row(
                    pos['symbol'],
                    f"[{size_color}]{pos['amount']}[/{size_color}]",
                    f"{pos['entryPrice']:.2f}",
                    f"{pos['markPrice']:.2f}",
                    f"{pos['marginType'].upper()} {pos['leverage']}x",
                    f"[{pnl_color}]{pnl:+.2f}[/{pnl_color}]"
                )
                
            console.print(table)
            
        if not orders:
            console.print("\n[#aaaaaa]No pending orders found.[/#aaaaaa]")
        else:
            console.print("") # spacing
            orders_table = Table(
                title="Pending Orders", 
                style="#00aaff", 
                box=rich.box.ROUNDED, 
                row_styles=["none", "dim"]
            )
            orders_table.add_column("ID", style="#aaaaaa", justify="right")
            orders_table.add_column("Symbol", style="#aaaaaa", no_wrap=True, justify="left")
            orders_table.add_column("Type", style="#aaaaaa", justify="left")
            orders_table.add_column("Side", justify="left")
            orders_table.add_column("Price/Stop", style="#aaaaaa", justify="right")
            orders_table.add_column("Quantity", style="#aaaaaa", justify="right")
            
            for ord_data in orders:
                side = ord_data.get('side', '')
                side_color = "#00ff00" if side == 'BUY' else "#ff0055"
                price_str = str(ord_data.get('price', '0'))
                
                ord_type = ord_data.get('origType') or ord_data.get('type') or ord_data.get('orderType') or 'UNKNOWN'
                
                if ord_type in ['STOP_MARKET', 'TAKE_PROFIT_MARKET', 'STOP', 'TAKE_PROFIT']:
                    price_str = f"Stop: {ord_data.get('stopPrice') or ord_data.get('triggerPrice') or '0'}"
                elif ord_type == 'LIMIT':
                    price_str = f"Limit: {ord_data.get('price', '0')}"
                
                orders_table.add_row(
                    str(ord_data.get('orderId', '')),
                    ord_data.get('symbol', ''),
                    ord_type,
                    f"[{side_color}]{side}[/{side_color}]",
                    price_str,
                    str(ord_data.get('origQty') or ord_data.get('quantity') or '')
                )
                
            console.print(orders_table)
        
    @staticmethod
    def prompt_close_or_cancel(positions, orders):
        """Prompts the user to select an open position to close or a pending order to cancel."""
        if not positions and not orders:
            console.print("[yellow]You have no open positions or pending orders to manage.[/yellow]")
            return None
            
        choices = []
        for pos in positions:
            choices.append(f"POS_{pos['symbol']}")
        for ord_data in orders:
            choices.append(f"ORD_{ord_data['orderId']}")
            
        choices.append("CANCEL")
        
        prompt_text = "\n[bold yellow]Select a position to close (POS_<Symbol>) or an order to cancel (ORD_<ID>)[/bold yellow]"
        
        selection = Prompt.ask(
            prompt_text,
            choices=choices,
            default="CANCEL"
        )
        
        if selection == "CANCEL":
            return None
            
        if selection.startswith("POS_"):
            return ("POSITION", selection.replace("POS_", ""))
        elif selection.startswith("ORD_"):
            return ("ORDER", selection.replace("ORD_", ""))
            
        return None

    @staticmethod
    def display_trade_history(client):
        """Fetches and renders the 20 most recent trades for a symbol."""
        console.print("\n[bold]Available Symbols:[/bold] BTCUSDT, XAUUSDT")
        symbol = Prompt.ask("Symbol to fetch history", choices=["BTCUSDT", "XAUUSDT"], default="BTCUSDT").upper()
        
        trades = client.get_trade_history(symbol)
        
        if not trades:
            console.print(f"[yellow]No trade history found for {symbol} or an error occurred.[/yellow]")
            return
            
        import datetime
        table = Table(title=f"Trade History ({symbol})", style="blue")
        table.add_column("Date/Time", style="cyan", no_wrap=True)
        table.add_column("Side", style="magenta")
        table.add_column("Exec Price", style="yellow")
        table.add_column("Qty", style="blue")
        table.add_column("Gross PnL", justify="right")
        table.add_column("Fees", style="red", justify="right")
        table.add_column("Net PnL", justify="right")
        
        for trade in trades:
            # Binance returns time in ms
            dt = datetime.datetime.fromtimestamp(trade['time'] / 1000.0).strftime('%Y-%m-%d %H:%M:%S')
            side = trade.get('side', "BUY" if trade.get('buyer') else "SELL")
            price = f"{float(trade['price']):.2f}"
            qty = f"{float(trade['qty']):.3f}"
            gross_pnl = float(trade['realizedPnl'])
            fee = float(trade.get('commission', 0))
            net_pnl = gross_pnl - fee
            
            pnl_color = "green" if gross_pnl >= 0 else "red"
            net_color = "green" if net_pnl >= 0 else "red"
            
            table.add_row(
                dt,
                side,
                price,
                qty,
                f"[{pnl_color}]{gross_pnl:.2f}[/{pnl_color}]",
                f"{fee:.4f}",
                f"[{net_color}]{net_pnl:.2f}[/{net_color}]"
            )
            
        console.print(table)
