import sqlite3
import json
import os

def fix_db_progress():
    db_path = "trading_platform.db"
    if not os.path.exists(db_path):
        print(f"Error: {db_path} does not exist.")
        return
        
    print(f"Connecting to database: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 1. Check all records before migration
    cursor.execute("SELECT id, ticker, status, progress, current_step, decision, recommendation FROM simulation_runs")
    rows = cursor.fetchall()
    print(f"Total runs found: {len(rows)}")
    
    modified_count = 0
    for row in rows:
        run_id, ticker, status, progress, current_step, decision, recommendation = row
        needs_fix = False
        new_progress = progress
        new_status = status
        new_step = current_step
        
        # Check progress bounds
        if progress > 100.0 or progress < 0.0:
            needs_fix = True
            new_progress = min(100.0, max(0.0, progress))
            print(f"-> Run {run_id} ({ticker}): progress {progress}% is out of bounds [0, 100]. Correcting to {new_progress}%.")
            
        # Check running but finished logic
        if status == "RUNNING" and (new_progress >= 99.0 or decision or recommendation):
            # If we have a decision or recommendation, it must be completed
            needs_fix = True
            new_status = "COMPLETED"
            new_progress = 100.0
            new_step = "분석 완료"
            print(f"-> Run {run_id} ({ticker}): status is RUNNING but has decision/high progress. Marking as COMPLETED with 100%.")
        elif status == "RUNNING" and new_progress < 99.0:
            # Running with normal progress but might be stale. We keep it as is or clamp it.
            if new_progress > 99.0:
                needs_fix = True
                new_progress = 99.0
                
        # If COMPLETED status but progress is not 100.0, sync it
        if status == "COMPLETED" and new_progress != 100.0:
            needs_fix = True
            new_progress = 100.0
            print(f"-> Run {run_id} ({ticker}): status is COMPLETED but progress is {progress}%. Updating to 100%.")
            
        if needs_fix:
            cursor.execute(
                "UPDATE simulation_runs SET status = ?, progress = ?, current_step = ? WHERE id = ?",
                (new_status, new_progress, new_step, run_id)
            )
            modified_count += 1
            
    conn.commit()
    print(f"Database migration completed. Total records modified: {modified_count}")
    
    # Check again
    cursor.execute("SELECT id, ticker, status, progress, current_step FROM simulation_runs")
    updated_rows = cursor.fetchall()
    print("\nUpdated Simulation Runs Table:")
    for row in updated_rows:
        print(f"ID: {row[0]} | Ticker: {row[1]} | Status: {row[2]} | Progress: {row[3]}% | Step: {row[4]}")
        
    conn.close()

if __name__ == "__main__":
    fix_db_progress()
