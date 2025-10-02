#!/usr/bin/env python3
"""
Generate sample log files for testing the log query script.
Files are sorted by user column as required.
"""

import csv
import random
from datetime import datetime, timedelta
from pathlib import Path


def generate_logs(start_date, num_days, num_users=99, logs_dir="data/logs"):
    """
    Generate sample log files.
    
    Args:
        start_date: Start date string 'YYYY-MM-DD'
        num_days: Number of days to generate
        num_users: Number of users (default 99 for user1-user99)
        logs_dir: Directory to save log files
    """
    logs_path = Path(logs_dir)
    logs_path.mkdir(exist_ok=True)
    
    apps = ['facebook', 'twitter', 'youtube', 'instagram', 'tiktok', 'linkedin']
    users = [f'user{i}' for i in range(1, num_users + 1)]
    
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    
    for day in range(num_days):
        current_date = start_dt + timedelta(days=day)
        log_file = logs_path / f"{current_date.date()}.log.csv"
        
        print(f"Generating {log_file}...")
        
        # Generate rows for this day
        rows = []
        
        # Each user may or may not have entries on this day
        for user in users:
            # 70% chance a user has entries on this day
            if random.random() > 0.7:
                continue
            
            # Each user uses 1-3 apps this day
            num_apps = random.randint(1, 3)
            user_apps = random.sample(apps, num_apps)
            
            for app in user_apps:
                # 1-5 entries per app per day
                num_entries = random.randint(1, 5)
                
                for _ in range(num_entries):
                    # Random time during the day
                    hour = random.randint(0, 23)
                    minute = random.randint(0, 59)
                    second = random.randint(0, 59)
                    
                    timestamp = current_date.replace(hour=hour, minute=minute, second=second)
                    timestamp_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
                    
                    # Generate random metrics
                    metrics = [random.randint(1, 1000) for _ in range(9)]
                    
                    row = [timestamp_str, user, app] + metrics
                    rows.append(row)
        
        # Sort by user (numerically), then timestamp (as specified in requirements)
        # Extract numeric part from user string for proper sorting
        def user_sort_key(row):
            user = row[1]
            # Extract number from 'userXX' format
            try:
                user_num = int(user.replace('user', ''))
            except ValueError:
                user_num = 0
            return (user_num, row[0])
        
        rows.sort(key=user_sort_key)
        
        # Write to file (no header as per requirements)
        with open(log_file, 'w', newline='') as f:
            writer = csv.writer(f)
            for row in rows:
                writer.writerow(row)
        
        print(f"  Generated {len(rows)} rows")
    
    print(f"\nGenerated {num_days} log files in '{logs_dir}' directory")


def main():
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python generate_logs.py <start_date> <num_days> [num_users]")
        print("Example: python generate_logs.py 2025-01-01 30 99")
        sys.exit(1)
    
    start_date = sys.argv[1]
    num_days = int(sys.argv[2])
    num_users = int(sys.argv[3]) if len(sys.argv) > 3 else 99
    
    generate_logs(start_date, num_days, num_users)


if __name__ == "__main__":
    main()