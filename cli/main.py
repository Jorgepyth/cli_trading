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
            order_data = InteractivePrompter.collect_order_details(trading_client)
            
            console.print("\n[bold yellow]Fetching current mark price...[/bold yellow]")
            mark_price = trading_client.get_mark_price(order_data['symbol'])
            
            if mark_price == 0:
                 console.print("[bold red]Error: Mark price could not be retrieved. Aborting.[/bold red]")
                 continue
                 
            # Use limit_price as entry price for LIMIT orders, mark_price for MARKET
            entry_price = order_data.get('limit_price') or mark_price
            
            # Fetch leverage for margin calculation in risk
            current_leverage = trading_client.get_leverage(order_data['symbol'])
            order_data['leverage'] = current_leverage if current_leverage else 20
            
            risk_analysis = risk_calc.calculate_pre_flight_risk(order_data, balance, entry_price)
            
            # Display Risk Table
            risk_table = Table(title="Pre-Flight Validation")
            risk_table.add_column("Metric", style="cyan")
            risk_table.add_column("Value", style="magenta")
            
            risk_table.add_row("Symbol & Side", f"{order_data.get('symbol', 'N/A')} {order_data.get('side', 'N/A')}")
            risk_table.add_row("Order Type", order_data.get('order_type', 'N/A'))
            risk_table.add_row("Entry Price", str(entry_price) + (" (LIMIT)" if order_data.get('order_type') == 'LIMIT' else " (Mark)"))
            risk_table.add_row("Order Size (USDT)", str(order_data.get('size_value', 'N/A')))
            risk_table.add_row("Target Gross PnL", str(risk_analysis.get('gross_pnl_target', 'N/A')))
            risk_table.add_row("Estimated Fees", str(risk_analysis.get('estimated_trading_fees', 'N/A')))
            risk_table.add_row("Net Expected PnL", str(risk_analysis.get('net_pnl_expected', 'N/A')))
            risk_table.add_row("Estimated Loss", f"[bold red]{risk_analysis.get('net_loss_expected', 'N/A')}[/bold red]")
            risk_pct = risk_analysis.get('risk_pct_equity_at_stake')
            risk_table.add_row("Risk as % of Equity", f"{risk_pct}%" if risk_pct is not None else "N/A")
            risk_table.add_row("Valid for Execution", "[green]YES[/green]" if risk_analysis.get('valid_for_execution', False) else "[red]NO[/red]")
            
            if not risk_analysis.get('valid_for_execution', False):
                risk_table.add_row("Rejection Reason", f"[bold red]{risk_analysis.get('rejection_reason', 'N/A')}[/bold red]")
        
            console.print(risk_table)

            if not risk_analysis['valid_for_execution']:
                console.print("[bold red]Execution BLOCKED based on risk constraints.[/bold red]")
                continue
                
            confirm = click.confirm("\nAre you absolutely sure you want to execute this trade?")

            if confirm:
                console.print("[bold green]Executing Trade...[/bold green]")
                # 1. Base quantity derivation (Truncation logic is now natively evaluated by BinanceTradingClient)
                if order_data.get('size_type') == 'ASSET':
                    quantity = order_data['size_value']
                else: # USDT
                    quantity = order_data['size_value'] / entry_price
                
                if quantity <= 0:
                    console.print("[bold red]Execution BLOCKED: Quantity is <= 0. Setup invalid.[/bold red]")
                    continue
                
                # 2. Ejecutar Orden de Entrada (MARKET o LIMIT)
                response = trading_client.execute_futures_order(
                    symbol=order_data['symbol'],
                    side=order_data['side'],
                    order_type=order_data['order_type'],
                    quantity=quantity,
                    price=order_data.get('limit_price')
                )
                
                if response:
                    console.print(f"[bold green]Entry Success! Response ID: {response.get('orderId')}[/bold green]")
                    
                    # 3. Determinar el lado opuesto para las órdenes de salida
                    exit_side = "SELL" if order_data['side'] == "BUY" else "BUY"
                    
                    # 4. Enforce TP / SL Conditionals via strictly monitored Try/Except block
                    try:
                        tp_price = order_data.get('tp_value')
                        if tp_price and tp_price > 0:
                            console.print(f"Setting Take Profit at {tp_price}...")
                            tp_response = trading_client.execute_futures_order(
                                symbol=order_data['symbol'],
                                side=exit_side,
                                order_type="TAKE_PROFIT_MARKET",
                                quantity=quantity, 
                                stop_price=tp_price,
                                reduce_only=True # INVARIANTE DE SEGURIDAD CRÍTICO
                            )
                            if not tp_response:
                                raise Exception("TP Order Execution Failed (Response None)")
                            console.print(f"[bold green]TP Set! ID: {tp_response.get('orderId')}[/bold green]")
                        
                        sl_price = order_data.get('sl_value')
                        if sl_price and sl_price > 0:
                            console.print(f"Setting Stop Loss at {sl_price}...")
                            sl_response = trading_client.execute_futures_order(
                                symbol=order_data['symbol'],
                                side=exit_side,
                                order_type="STOP_MARKET",
                                quantity=quantity, 
                                stop_price=sl_price,
                                reduce_only=True # INVARIANTE DE SEGURIDAD CRÍTICO
                            )
                            if not sl_response:
                                raise Exception("SL Order Execution Failed (Response None)")
                            console.print(f"[bold green]SL Set! ID: {sl_response.get('orderId')}[/bold green]")
                            
                    except Exception as e:
                        console.print(f"[bold red]CRITICAL FAULT: TP/SL routing failed ({e}). Position liquidated automatically to prevent exposure.[/bold red]")
                        # Kill-Switch Trigger
                        kill_response = trading_client.execute_futures_order(
                            symbol=order_data['symbol'],
                            side=exit_side,
                            order_type="MARKET",
                            quantity=quantity,
                            reduce_only=False
                        )

                    balance = trading_client.get_account_balance()
                else:
                     console.print("[bold red]Entry Execution Failed. Halting.[/bold red]")
            else:
                console.print("[yellow]Trade Cancelled.[/yellow]")
                
        elif choice == '3':
            positions = trading_client.get_open_positions()
            orders = trading_client.get_open_orders()
            
            # Show the dashboard first so they know what to pick
            InteractivePrompter.display_status_dashboard(trading_client)
            
            selection = InteractivePrompter.prompt_close_or_cancel(positions, orders)
            
            if selection:
                action_type, target = selection
                
                if action_type == "POSITION":
                    symbol_to_close = target
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
                            
                elif action_type == "ORDER":
                    order_id = int(target)
                    ord_to_cancel = next((o for o in orders if o['orderId'] == order_id), None)
                    if ord_to_cancel:
                        symbol = ord_to_cancel['symbol']
                        console.print(f"[bold yellow]Cancelling order {order_id} for {symbol}[/bold yellow]")
                        confirm = click.confirm("Confirm cancelling this order?")
                        
                        if confirm:
                            response = trading_client.cancel_order(symbol=symbol, order_id=order_id)
                            # response usually contains {'clientOrderId': '...', 'cumQty': '0', 'cumQuote': '0', 'executedQty': '0', 'orderId': ..., 'origQty': '...', 'price': '...', 'reduceOnly': False, 'side': '...', 'status': 'CANCELED', ...}
                            if response and response.get('status') == 'CANCELED':
                                console.print(f"[bold green]Successfully cancelled order! Response ID: {response.get('orderId')}[/bold green]")
                            else:
                                console.print("[bold red]Failed to cancel order.[/bold red]")
                        else:
                            console.print("[yellow]Cancel cancelled.[/yellow]")
                        
        elif choice == '4':
            console.print("[bold green]Exiting B.L.A.S.T Terminal. Goodbye![/bold green]")
            break



if __name__ == '__main__':
    run_cli()
