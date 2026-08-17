import time
import subprocess
import sys
import os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCANNER_SCRIPT = os.path.join(BASE_DIR, "scanner.py")

def main():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting Remote Job Scanner Daemon...")
    
    while True:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Triggering scan execution...")
        try:
            # Execute scanner.py under the same python interpreter
            result = subprocess.run(
                [sys.executable, SCANNER_SCRIPT], 
                cwd=BASE_DIR, 
                capture_output=True, 
                text=True
            )
            
            # Print the output from scanner.py to the daemon log
            if result.stdout:
                print(result.stdout.strip())
            if result.stderr:
                print(f"ERROR: {result.stderr.strip()}", file=sys.stderr)
                
        except Exception as e:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Exception in daemon execution loop: {e}", file=sys.stderr)
            
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Scan finished. Sleeping for 1 hour (3600 seconds)...")
        sys.stdout.flush()
        
        # Sleep for 1 hour (3600 seconds)
        time.sleep(3600)

if __name__ == "__main__":
    main()
