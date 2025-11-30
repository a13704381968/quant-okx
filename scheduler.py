import time
import subprocess
import sys
import os
from quant_engine.db import init_db, get_db_connection, update_strategy_status

# Ensure we can import from current directory
sys.path.append(os.getcwd())

PYTHON_EXECUTABLE = sys.executable
STRATEGY_RUNNER_SCRIPT = os.path.join(os.getcwd(), 'strategy_runner.py')

running_processes = {}

def start_strategy_process(strategy_name, symbol, leverage, interval='1H'):
    print(f"Starting strategy process: {strategy_name} {symbol} leverage={leverage} interval={interval}")
    try:
        # Start the strategy runner as a subprocess
        process = subprocess.Popen(
            [PYTHON_EXECUTABLE, STRATEGY_RUNNER_SCRIPT, strategy_name, symbol, str(leverage), interval],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        running_processes[strategy_name] = process
        print(f"Started process {process.pid} for {strategy_name}")
    except Exception as e:
        print(f"Failed to start strategy {strategy_name}: {e}")
        update_strategy_status(strategy_name, 'ERROR', str(e))

def stop_strategy_process(strategy_name):
    if strategy_name in running_processes:
        print(f"Stopping strategy process: {strategy_name}")
        process = running_processes[strategy_name]
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
        del running_processes[strategy_name]
        print(f"Stopped process for {strategy_name}")

def monitor_processes():
    # Check for crashed processes
    for name, process in list(running_processes.items()):
        if process.poll() is not None:
            # Process has exited
            stdout, stderr = process.communicate()
            print(f"Process for {name} exited. Return code: {process.returncode}")
            if stdout:
                print(f"STDOUT: {stdout}")
            if stderr:
                print(f"STDERR: {stderr}")
            
            del running_processes[name]
            
            # Update DB status if it was supposed to be running
            # We need to check if it was stopped intentionally or crashed
            # For now, assume crash if it disappears from here but DB says RUNNING
            update_strategy_status(name, 'ERROR', f"Process exited unexpectedly. Stderr: {stderr[-200:] if stderr else ''}")

def main():
    print("Starting Scheduler...")
    init_db()
    
    while True:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM strategy_status")
            strategies = cursor.fetchall()
            conn.close()
            
            db_strategies = {row['name']: row for row in strategies}
            
            # 1. Start strategies that should be running but aren't
            for name, data in db_strategies.items():
                if data['status'] == 'RUNNING':
                    if name not in running_processes:
                        interval = data['interval'] if 'interval' in data.keys() else '1H'
                        start_strategy_process(name, data['symbol'], data['leverage'], interval)
            
            # 2. Stop strategies that shouldn't be running but are
            for name in list(running_processes.keys()):
                if name not in db_strategies or db_strategies[name]['status'] != 'RUNNING':
                    stop_strategy_process(name)
            
            # 3. Monitor running processes
            monitor_processes()
            
            time.sleep(2)
            
        except Exception as e:
            print(f"Scheduler loop error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
