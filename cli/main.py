import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.align import Align
from rich.prompt import Prompt, Confirm
import rich.box

from cli.auth import local_auth
from cli.prompter import InteractivePrompter
from tools.binance_client import BinanceTradingClient
from tools.risk_calculator import RiskCalculator

console = Console()

@click.command()
@click.option('--prod', is_flag=True, help='Run against Binance Production API instead of Testnet')
@click.option('--sub', is_flag=True, help='Run against Binance Sub-Account API on Production')
def run_cli(prod, sub):
    """
    Trading Terminal Interactive Trading CLI for Binance Futures.
    """
    # 1. Zero Trust - Local Auth
    if not local_auth():
        console.print("[bold #ff0055]Authentication failed. Exiting.[/bold #ff0055]")
        return
        
    env_str = "SUBACCOUNT" if sub else ("MAINNET" if prod else "TESTNET")
    
    console.print(Panel(f"[bold #00ff00]Trading Terminal Authenticated.[/bold #00ff00]\n"
                        f"Environment: [bold #ff0055]{env_str}[/bold #ff0055]"))

    # 2. Init Layer 3 atomic tools
    try:
        trading_client = BinanceTradingClient(env=env_str)
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
        console.print()
        menu_text = (
            "[#aaaaaa]1. View Status[/#aaaaaa]\n"
            "[#aaaaaa]2. Open Trade[/#aaaaaa]\n"
            "[#aaaaaa]3. Close Trade[/#aaaaaa]\n"
            "[#aaaaaa]4. Trade History[/#aaaaaa]\n"
            "[#aaaaaa]5. Exit[/#aaaaaa]"
        )
        menu_panel = Panel(
            Align.center(menu_text),
            title="[bold #00aaff]TRADING TERMINAL - MAIN MENU[/bold #00aaff]",
            border_style="#00aaff",
            expand=False
        )
        console.print(Align.center(menu_panel))
        console.print()
        
        choice = Prompt.ask("[#00aaff]❯[/#00aaff] Select action", choices=['1', '2', '3', '4', '5'])
        
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
            risk_table = Table(title="Pre-Flight Validation", box=rich.box.HEAVY)
            risk_table.add_column("Metric", style="#00aaff")
            risk_table.add_column("Value", style="#aaaaaa")
            
            risk_table.add_row("Symbol & Side", f"{order_data.get('symbol', 'N/A')} {order_data.get('side', 'N/A')}")
            risk_table.add_row("Order Type", order_data.get('order_type', 'N/A'))
            risk_table.add_row("Entry Price", str(entry_price) + (" (LIMIT)" if order_data.get('order_type') == 'LIMIT' else " (Mark)"))
            risk_table.add_row("Order Size (USDT)", str(order_data.get('size_value', 'N/A')))
            
            risk_table.add_section() # Separate Order Specs from Risk Metrics
            
            risk_table.add_row("Target Gross PnL", str(risk_analysis.get('gross_pnl_target', 'N/A')))
            risk_table.add_row("Estimated Fees", str(risk_analysis.get('estimated_trading_fees', 'N/A')))
            risk_table.add_row("Net Expected PnL", str(risk_analysis.get('net_pnl_expected', 'N/A')))
            risk_table.add_row("Estimated Loss", f"[#ff0055]{risk_analysis.get('net_loss_expected', 'N/A')}[/#ff0055]")
            risk_pct = risk_analysis.get('risk_pct_equity_at_stake')
            risk_table.add_row("Risk as % of Equity", f"{risk_pct}%" if risk_pct is not None else "N/A")
            
            is_valid = risk_analysis.get('valid_for_execution', False)
            valid_style = "none" if is_valid else "bold #ffffff on #ff0000"
            risk_table.add_row(
                "Valid for Execution", 
                "[#00ff00]YES[/#00ff00]" if is_valid else "[#ffffff on #ff0000]NO[/#ffffff on #ff0000]",
                style=valid_style
            )
            
            if not is_valid:
                risk_table.add_row(
                    "Rejection Reason", 
                    f"[#ffffff on #ff0000]{risk_analysis.get('rejection_reason', 'N/A')}[/#ffffff on #ff0000]", 
                    style="bold #ffffff on #ff0000"
                )
        
            console.print(risk_table)

            if not risk_analysis['valid_for_execution']:
                console.print("[bold #ff0055]Execution BLOCKED based on risk constraints.[/bold #ff0055]")
                continue
                
            confirm = Confirm.ask("\nAre you absolutely sure you want to execute this trade?")

            if confirm:
                console.print("[bold #00ff00]Executing Trade...[/bold #00ff00]")
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
                    
                    # Verified Quantity Tracking
                    import time
                    executed_qty = float(response.get('executedQty', 0.0))
                    original_qty = quantity
                    
                    # Rigid block checking FILLED status for LIMIT/unfilled orders
                    if order_data['order_type'] == 'LIMIT' or executed_qty == 0.0:
                        console.print("[yellow]Waiting for order fulfillment to route TP/SL...[/yellow]")
                        max_polls = 10
                        success_fill = False
                        try:
                            for poll in range(max_polls):
                                time.sleep(2)
                                open_positions = trading_client.get_open_positions()
                                target_pos = next((p for p in open_positions if p['symbol'] == order_data['symbol']), None)
                                if target_pos and abs(target_pos['amount']) >= (quantity * 0.9):
                                    console.print("[green]Confirmation: Position active.[/green]")
                                    executed_qty = abs(target_pos['amount'])
                                    success_fill = True
                                    break
                        finally:
                            if not success_fill:
                                 console.print("[yellow]Timeout or interrupt waiting for fill. Active LIMIT remains on the orderbook, but ABORTING TP/SL concurrent routing to prevent naked exposure.[/yellow]")
                                 trading_client.cancel_order(order_data['symbol'], response.get('orderId'))
                                 console.print("[yellow]Original LIMIT order explicitly cancelled.[/yellow]")
                                 continue
                    elif executed_qty == 0.0 and order_data['order_type'] == 'MARKET':
                        time.sleep(1)
                        open_positions = trading_client.get_open_positions()
                        target_pos = next((p for p in open_positions if p['symbol'] == order_data['symbol']), None)
                        if target_pos:
                            executed_qty = abs(target_pos['amount'])
                    
                    if executed_qty <= 0.0:
                        console.print("[bold red]CRITICAL: Unable to verify position Amt from exchange ledger. Halting to prevent desynchronization.[/bold red]")
                        # Cancel the order just in case it's in a weird state
                        trading_client.cancel_order(order_data['symbol'], response.get('orderId'))
                        continue
                    
                    safe_quantity = executed_qty
                    
                    # 4. Enforce TP / SL Conditionals via strictly monitored Try/Except block
                    try:
                        tp_price = order_data.get('tp_value')
                        if tp_price and tp_price > 0:
                            console.print(f"Setting Take Profit at {tp_price}...")
                            tp_response = trading_client.execute_futures_order(
                                symbol=order_data['symbol'],
                                side=exit_side,
                                order_type="TAKE_PROFIT_MARKET",
                                quantity=safe_quantity, 
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
                                quantity=safe_quantity, 
                                stop_price=sl_price,
                                reduce_only=True # INVARIANTE DE SEGURIDAD CRÍTICO
                            )
                            if not sl_response:
                                raise Exception("SL Order Execution Failed (Response None)")
                            console.print(f"[bold green]SL Set! ID: {sl_response.get('orderId')}[/bold green]")
                            
                    except Exception as e:
                        console.print(f"[bold red]CRITICAL FAULT: TP/SL routing failed ({e}). Position liquidated automatically to prevent exposure.[/bold red]")
                        # Kill-Switch Trigger with Exponential Backoff
                        console.print("[yellow]Cancelling all open orders to clear book before MARKET liquidation...[/yellow]")
                        trading_client.cancel_all_open_orders(order_data['symbol'])
                        max_retries = 3
                        for attempt in range(max_retries):
                            try:
                                kill_response = trading_client.execute_futures_order(
                                    symbol=order_data['symbol'],
                                    side=exit_side,
                                    order_type="MARKET",
                                    quantity=safe_quantity,
                                    reduce_only=True # Explicitly True to prevent reversals
                                )
                                if kill_response:
                                    console.print(f"[bold green]Kill-Switch successful on attempt {attempt+1}.[/bold green]")
                                    break
                                raise Exception("Empty response inside Kill-Switch API wrapper")
                            except Exception as ke:
                                if attempt < max_retries - 1:
                                    sleep_time = 1.5 ** attempt
                                    console.print(f"[yellow]Kill-Switch failure ({ke}). Retrying in {sleep_time:.2f}s...[/yellow]")
                                    time.sleep(sleep_time)
                                else:
                                    console.print("[bold red]FATAL: Kill-Switch completely failed after max retries. Manual intervention REQUIRED.[/bold red]")

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
            
            selections = InteractivePrompter.prompt_close_or_cancel(positions, orders)
            
            if selections:
                console.print(f"\n[bold yellow]You have selected {len(selections)} action(s) to execute.[/bold yellow]")
                confirm = Confirm.ask("Execute all these closing actions now?")
                
                if not confirm:
                    console.print("[yellow]Batch execution cancelled.[/yellow]")
                    continue
                    
                for action_type, target in selections:
                    if action_type == "POSITION":
                        symbol_to_close = target
                        pos_to_close = next((p for p in positions if p['symbol'] == symbol_to_close), None)
                        if pos_to_close:
                            amount = abs(pos_to_close['amount'])
                            side = "SELL" if pos_to_close['amount'] > 0 else "BUY"
                            
                            console.print(f"[bold yellow]Closing position for {symbol_to_close} with MARKET {side} of {amount}...[/bold yellow]")
                            
                            response = trading_client.execute_futures_order(
                                symbol=symbol_to_close,
                                side=side,
                                order_type="MARKET",
                                quantity=amount,
                                reduce_only=True
                            )
                            if response:
                                 console.print(f"[bold green]Successfully closed position! Response ID: {response.get('orderId')}[/bold green]")
                            else:
                                 console.print("[bold red]Failed to close position.[/bold red]")
                                 
                    elif action_type == "ORDER":
                        order_id = int(target)
                        ord_to_cancel = next((o for o in orders if o['orderId'] == order_id), None)
                        if ord_to_cancel:
                            symbol = ord_to_cancel['symbol']
                            console.print(f"[bold yellow]Cancelling order {order_id} for {symbol}...[/bold yellow]")
                            
                            response = trading_client.cancel_order(symbol=symbol, order_id=order_id)
                            # Any truthy response means the API accepted the cancellation (Algo orders return different payload structures)
                            if response:
                                _id = response.get('orderId') or response.get('algoId') or order_id
                                console.print(f"[bold green]Successfully cancelled order! Response ID: {_id}[/bold green]")
                            else:
                                console.print("[bold red]Failed to cancel order. (Or order already executed/cancelled)[/bold red]")
                
                balance = trading_client.get_account_balance()
                        
        elif choice == '4':
            InteractivePrompter.display_trade_history(trading_client)
            
        elif choice == '5':
            console.print("[bold #00ff00]Exiting Trading Terminal. Goodbye![/bold #00ff00]")
            break



if __name__ == '__main__':
    run_cli()
