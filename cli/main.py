import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from cli.auth import local_auth
from cli.prompter import InteractivePrompter
from tools.binance_client import BinanceTradingClient
from tools.risk_calculator import RiskCalculator

console = Console()

@click.command()
@click.option('--prod', is_flag=True, help='Run against Binance Production API instead of Testnet')
def run_cli(prod):
    """
    B.L.A.S.T. Terminal Interactive Trading CLI for Binance Futures.
    """
    # 1. Zero Trust - Local Auth
    if not local_auth():
        console.print("[bold red]Authentication failed. Exiting.[/bold red]")
        return
        
    console.print(Panel("[bold green]B.L.A.S.T Terminal Authenticated.[/bold green]\n"
                        "Environment: " + ("[bold red]PRODUCTION[/bold red]" if prod else "[bold yellow]TESTNET[/bold yellow]")))

    # 2. Init Layer 3 atomic tools
    try:
        trading_client = BinanceTradingClient(use_testnet=not prod)
        risk_calc = RiskCalculator()
    except ValueError as e:
        console.print(f"[bold red]Configuration Error:[/bold red] {e}")
        return

    # Check Connectivity
    console.print("Pinging exchange...")
    ping_result = trading_client.ping()
    if ping_result is None:
        console.print("[bold red]Critical Error: Cannot connect to exchange.[/bold red]")
        return
        
    balance = trading_client.get_account_balance()
    console.print(f"Account Balance: [cyan]{balance}[/cyan] USDT")

    # Main Menu Loop
    while True:
        console.print("\n" + "="*50, style="blue")
        console.print("[bold cyan]B.L.A.S.T. TERMINAL - MAIN MENU[/bold cyan]")
        console.print("="*50, style="blue")
        console.print("1. View Status")
        console.print("2. Open Trade")
        console.print("3. Close Trade")
        console.print("4. Exit\n")
        
        choice = click.prompt("Select an action", type=click.Choice(['1', '2', '3', '4']))
        
        if choice == '1':
            InteractivePrompter.display_status_dashboard(trading_client)
            
        elif choice == '2':
            # Interactive Data Collection
            order_data = InteractivePrompter.collect_order_details()
            
            console.print("\n[bold yellow]Fetching current mark price...[/bold yellow]")
            mark_price = trading_client.get_mark_price(order_data['symbol'])
            
            if mark_price == 0:
                 console.print("[bold red]Error: Mark price could not be retrieved. Aborting.[/bold red]")
                 continue
                 
            risk_analysis = risk_calc.calculate_pre_flight_risk(order_data, balance, mark_price)
            
            # Display Risk Table
            risk_table = Table(title="Pre-Flight Validation")
            risk_table.add_column("Metric", style="cyan")
            risk_table.add_column("Value", style="magenta")
            
            risk_table.add_row("Symbol & Side", f"{order_data['symbol']} {order_data['side']}")
            risk_table.add_row("Entry Mark Price", str(mark_price))
            risk_table.add_row("Order Size (USDT)", str(order_data['size_value']))
            risk_table.add_row("Target Gross PnL", str(risk_analysis['gross_pnl_target']))
            risk_table.add_row("Estimated Fees", str(risk_analysis['estimated_trading_fees']))
            risk_table.add_row("Net Expected PnL", str(risk_analysis['net_pnl_expected']))
            risk_table.add_row("Risk as % of Equity", f"{risk_analysis['risk_pct_equity_at_stake']}%")
            risk_table.add_row("Valid for Execution", "[green]YES[/green]" if risk_analysis['valid_for_execution'] else "[red]NO[/red]")
            
            if not risk_analysis['valid_for_execution']:
                risk_table.add_row("Rejection Reason", f"[bold red]{risk_analysis['rejection_reason']}[/bold red]")
        
            console.print(risk_table)

            if not risk_analysis['valid_for_execution']:
                console.print("[bold red]Execution BLOCKED based on risk constraints.[/bold red]")
                continue
                
            confirm = click.confirm("\nAre you absolutely sure you want to execute this trade?")

            if confirm:
                console.print("[bold green]Executing Trade...[/bold green]")
                quantity = round(order_data['size_value'] / mark_price, 3) 
                
                response = trading_client.execute_futures_order(
                    symbol=order_data['symbol'],
                    side=order_data['side'],
                    order_type=order_data['order_type'],
                    quantity=quantity
                )
                
                if response:
                     console.print(f"[bold green]Success! Response ID: {response.get('orderId')}[/bold green]")
                     balance = trading_client.get_account_balance() # update balance
                else:
                     console.print("[bold red]Execution Failed.[/bold red]")
            else:
                console.print("[yellow]Trade Cancelled.[/yellow]")
                
        elif choice == '3':
            positions = trading_client.get_open_positions()
            symbol_to_close = InteractivePrompter.prompt_close_trade(positions)
            
            if symbol_to_close:
                # Find position details
                pos_to_close = next((p for p in positions if p['symbol'] == symbol_to_close), None)
                if pos_to_close:
                    amount = abs(pos_to_close['amount'])
                    side = "SELL" if pos_to_close['amount'] > 0 else "BUY"
                    
                    console.print(f"[bold yellow]Closing position for {symbol_to_close} with MARKET {side} of {amount}[/bold yellow]")
                    confirm = click.confirm("Confirm closing this position?")
                    
                    if confirm:
                        response = trading_client.execute_futures_order(
                            symbol=symbol_to_close,
                            side=side,
                            order_type="MARKET",
                            quantity=amount,
                            reduce_only=True
                        )
                        if response:
                             console.print(f"[bold green]Successfully closed position! Response ID: {response.get('orderId')}[/bold green]")
                             balance = trading_client.get_account_balance()
                        else:
                             console.print("[bold red]Failed to close position.[/bold red]")
                    else:
                        console.print("[yellow]Close cancelled.[/yellow]")
                        
        elif choice == '4':
            console.print("[bold green]Exiting B.L.A.S.T Terminal. Goodbye![/bold green]")
            break



if __name__ == '__main__':
    run_cli()
