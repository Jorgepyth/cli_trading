import click
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.console import Console

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
            console.print("[bold yellow]LIMIT order selected — you must specify the exact price at which to fill.[/bold yellow]")
            order_data['limit_price'] = float(Prompt.ask("Limit Price (USDT)"))
        else:
            order_data['limit_price'] = None
        
        # Change 2: Fetch and display current leverage before asking for confirmation
        if trading_client:
            console.print("\n[bold yellow]Fetching current leverage from exchange...[/bold yellow]")
            current_leverage = trading_client.get_leverage(order_data['symbol'])
            if current_leverage:
                console.print(f"  Current leverage for [cyan]{order_data['symbol']}[/cyan]: [bold magenta]{current_leverage}x[/bold magenta]")
            else:
                console.print("  [yellow]Could not fetch current leverage.[/yellow]")
        order_data['leverage_confirmed'] = Confirm.ask("Is your leverage already set correctly on the exchange?")
        
        if not order_data['leverage_confirmed']:
             click.secho("Please set your leverage manually on the exchange first.", fg="red")
             raise SystemExit()

        order_data['size_type'] = Prompt.ask("Size Type", choices=["USDT", "ASSET"], default="USDT").upper()
        order_data['size_value'] = float(Prompt.ask("Size Value"))
        
        # Change 3: Show all TP/SL type options (PRICE and PNL)
        console.print("\n[bold]TP/SL Types:[/bold]")
        console.print("  [cyan]PRICE[/cyan] - Set Take Profit and Stop Loss as exact price levels")
        console.print("  [cyan]PNL[/cyan]   - Set Take Profit and Stop Loss as target PnL amounts in USDT")
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
        
        console.print(f"\n[bold cyan]Account Balance:[/bold cyan] {balance:.2f} USDT\n")
        
        if not positions:
            console.print("[yellow]No open positions found.[/yellow]")
        else:
            table = Table(title="Open Positions", style="blue")
            table.add_column("Symbol", style="cyan", no_wrap=True)
            table.add_column("Size", style="magenta")
            table.add_column("Entry Price", style="green")
            table.add_column("Mark Price", style="yellow")
            table.add_column("Margin/Leverage", style="blue")
            table.add_column("Unrealized PnL", justify="right")
            
            for pos in positions:
                pnl_color = "green" if pos['unRealizedProfit'] >= 0 else "red"
                size_color = "green" if pos['amount'] > 0 else "red"
                table.add_row(
                    pos['symbol'],
                    f"[{size_color}]{pos['amount']}[/{size_color}]",
                    f"{pos['entryPrice']:.2f}",
                    f"{pos['markPrice']:.2f}",
                    f"{pos['marginType'].upper()} {pos['leverage']}x",
                    f"[{pnl_color}]{pos['unRealizedProfit']:.2f}[/{pnl_color}]"
                )
                
            console.print(table)
            
        if not orders:
            console.print("\n[yellow]No pending orders found.[/yellow]")
        else:
            console.print("") # spacing
            orders_table = Table(title="Pending Orders", style="magenta")
            orders_table.add_column("ID", style="cyan")
            orders_table.add_column("Symbol", style="cyan", no_wrap=True)
            orders_table.add_column("Type", style="yellow")
            orders_table.add_column("Side", style="blue")
            orders_table.add_column("Price/Stop", style="green")
            orders_table.add_column("Quantity", style="magenta")
            
            for ord_data in orders:
                side_color = "green" if ord_data['side'] == 'BUY' else "red"
                price_str = str(ord_data['price'])
                if ord_data['origType'] in ['STOP_MARKET', 'TAKE_PROFIT_MARKET', 'STOP', 'TAKE_PROFIT']:
                    price_str = f"Stop: {ord_data.get('stopPrice', '0')}"
                elif ord_data['origType'] == 'LIMIT':
                    price_str = f"Limit: {ord_data.get('price', '0')}"
                
                orders_table.add_row(
                    str(ord_data['orderId']),
                    ord_data['symbol'],
                    ord_data['origType'],
                    f"[{side_color}]{ord_data['side']}[/{side_color}]",
                    price_str,
                    str(ord_data['origQty'])
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
