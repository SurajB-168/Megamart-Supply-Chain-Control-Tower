import os
import sys
import argparse
import time
import pandas as pd
from datetime import datetime

# Add src to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import pipeline modules conditionally inside functions or globally with try-except to avoid failure if files don't exist yet
def run_step(step_name, func, log_file, *args, **kwargs):
    """Run a pipeline step, measure time, log result, and handle errors."""
    print(f"\n{'='*50}")
    print(f"🚀 Starting Step: {step_name}")
    print(f"{'='*50}")
    
    start_time = time.time()
    status = "SUCCESS"
    error_msg = ""
    
    try:
        func(*args, **kwargs)
    except Exception as e:
        status = "FAILED"
        error_msg = str(e)
        print(f"\n❌ Error in {step_name}: {error_msg}")
    
    end_time = time.time()
    duration = round(end_time - start_time, 2)
    
    # Log to CSV
    log_data = {
        'run_date': [datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
        'step_name': [step_name],
        'status': [status],
        'duration_seconds': [duration],
        'error_message': [error_msg]
    }
    df_log = pd.DataFrame(log_data)
    
    # Append to CSV
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    if os.path.exists(log_file):
        df_log.to_csv(log_file, mode='a', header=False, index=False)
    else:
        df_log.to_csv(log_file, mode='w', header=True, index=False)
        
    if status == "SUCCESS":
        print(f"✅ Finished {step_name} in {duration}s")
    
    return status, duration

def print_windows_scheduler_instructions(script_path):
    print("\n" + "="*60)
    print("⏰ WINDOWS TASK SCHEDULER SETUP")
    print("="*60)
    print("To run this pipeline daily at 6:00 AM, open Command Prompt as Administrator")
    print("and run the following command:\n")
    
    python_exe = sys.executable
    command = f'schtasks /create /tn "MegaMart_Daily_Pipeline" /tr "{python_exe} \\"{script_path}\\" --forecast-only" /sc daily /st 06:00'
    print(command)
    print("\nTo remove the task later, run:")
    print('schtasks /delete /tn "MegaMart_Daily_Pipeline" /f')
    print("="*60)

def main():
    parser = argparse.ArgumentParser(description="MegaMart Daily Pipeline Orchestrator")
    parser.add_argument("--full", action="store_true", help="Run full pipeline including historical data extraction")
    parser.add_argument("--forecast-only", action="store_true", help="Only extract forecast + predict + alert (default daily run)")
    parser.add_argument("--skip-email", action="store_true", help="Skip email alerts step")
    args = parser.parse_args()
    
    # Default behavior is forecast-only if full is not provided
    is_full_run = args.full

    print(f"🌟 Starting MegaMart Pipeline Orchestrator - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 🌟")
    
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    log_file = os.path.join(base_dir, 'reports', 'pipeline_log.csv')
    
    # Track overall summary
    summary = []
    
    # Dynamically import modules
    try:
        import importlib
        # Ensure we can import modules
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    except ImportError as e:
        print(f"Failed to setup imports: {e}")
        return

    # STEP 1: Extract Weather
    try:
        mod_weather = importlib.import_module('02_extract_weather')
        mode = "full" if is_full_run else "forecast"
        status, dur = run_step("Extract Weather Forecast", mod_weather.main, log_file, mode=mode)
        summary.append(("Extract Weather Forecast", status, dur))
    except Exception as e:
        print(f"❌ Failed to load Step 1 module: {e}")
        summary.append(("Extract Weather Forecast", "FAILED (Import)", 0))
        if status == "FAILED": return # Stop pipeline if critical step fails (optional logic)

    # STEP 2: Transform & Load Data
    try:
        mod_transform = importlib.import_module('03_transform_load')
        status, dur = run_step("Transform & Load Data", mod_transform.main, log_file)
        summary.append(("Transform & Load Data", status, dur))
    except Exception as e:
        print(f"❌ Failed to load Step 2 module: {e}")
        summary.append(("Transform & Load Data", "FAILED (Import)", 0))

    # STEP 3: Generate Predictions & Risk Analysis
    try:
        mod_predict = importlib.import_module('05_predict_and_risk')
        status, dur = run_step("Predict & Risk Analysis", mod_predict.main, log_file)
        summary.append(("Predict & Risk Analysis", status, dur))
    except Exception as e:
        print(f"❌ Failed to load Step 3 module: {e}")
        summary.append(("Predict & Risk Analysis", "FAILED (Import)", 0))

    # STEP 4: Send Email Alerts
    if not args.skip_email:
        try:
            mod_email = importlib.import_module('06_email_alerts')
            status, dur = run_step("Email Alerts", mod_email.main, log_file)
            summary.append(("Email Alerts", status, dur))
        except Exception as e:
            print(f"❌ Failed to load Step 4 module: {e}")
            summary.append(("Email Alerts", "FAILED (Import)", 0))
    else:
        print("\n⏭️ Skipping Email Alerts (--skip-email flag provided)")
        summary.append(("Email Alerts", "SKIPPED", 0))

    # PRINT SUMMARY
    print("\n" + "="*50)
    print("📊 PIPELINE EXECUTION SUMMARY")
    print("="*50)
    for step, status, dur in summary:
        icon = "✅" if status == "SUCCESS" else ("⏭️" if status == "SKIPPED" else "❌")
        print(f"{icon} {step.ljust(30)} | {status.ljust(10)} | {dur}s")
    print("="*50)
    
    print_windows_scheduler_instructions(os.path.abspath(__file__))

if __name__ == "__main__":
    main()
