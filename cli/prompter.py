import click
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.console import Console

console = Console()

class InteractivePrompter:
    @staticmethod
    def collect_order_details():
        """
        Interactive flow to gather order schema details.
        Matches the Order Request Schema from Protocol 0.
        """
        order_data = {}
        
        order_data['symbol'] = Prompt.ask("Symbol", default="BTCUSDT").upper()
        order_data['order_type'] = Prompt.ask("Order Type", choices=["MARKET", "LIMIT"], default="MARKET").upper()
        order_data['side'] = Prompt.ask("Side", choices=["BUY", "SELL"], default="BUY").upper()
        order_data['leverage_confirmed'] = Confirm.ask("Is your leverage already set correctly on the exchange?")
        
        if not order_data['leverage_confirmed']:
             click.secho("Please set your leverage manually on the exchange first.", fg="red")
             raise SystemExit()

        order_data['size_type'] = Prompt.ask("Size Type", choices=["USDT", "ASSET"], default="USDT").upper()
        order_data['size_value'] = float(Prompt.ask("Size Value"))
        
        order_data['tp_sl_type'] = Prompt.ask("Take-Profit / Stop-Loss Type", choices=["PRICE"], default="PRICE").upper()
        
        order_data['tp_value'] = float(Prompt.ask("Take Profit Price", default="0.0"))
        order_data['sl_value'] = float(Prompt.ask("Stop Loss Price", default="0.0"))
        
        return order_data
        
    @staticmethod
    def display_status_dashboard(client):
        """Fetches and displays account balance and open positions."""
        balance = client.get_account_balance()
        positions = client.get_open_positions()
        
        console.print(f"\n[bold cyan]Account Balance:[/bold cyan] {balance:.2f} USDT\n")
        
        if not positions:
            console.print("[yellow]No open positions found.[/yellow]")
            return
            
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
        
    @staticmethod
    def prompt_close_trade(positions):
        """Prompts the user to select an open position to close."""
        if not positions:
            console.print("[yellow]You have no open positions to close.[/yellow]")
            return None
            
        choices = [pos['symbol'] for pos in positions]
        choices.append("CANCEL")
        
        symbol_to_close = Prompt.ask(
            "\n[bold yellow]Select symbol to close completely (MARKET)[/bold yellow]",
            choices=choices,
            default="CANCEL"
        )
        
        if symbol_to_close == "CANCEL":
            return None
            
        return symbol_to_close
