import os
import csv
from datetime import datetime, timedelta
import random

# Directory for logs
log_dir = "data/logs"
os.makedirs(log_dir, exist_ok=True)

# Parameters
start_date = datetime(2025, 1, 1)
end_date = datetime(2025, 1, 5)  # generate 5 days of logs
users = ["user1", "user2", "user3", "user4"]
apps = ["facebook", "youtube", "twitter", "instagram", "spotify"]
rows_per_day = 50  # number of rows per log file

# Generate data
current_date = start_date
while current_date <= end_date:
    log_file = os.path.join(log_dir, f"{current_date.strftime('%Y-%m-%d')}.log.csv")
    with open(log_file, "w", newline="") as f:
        writer = csv.writer(f)
        # Write header
        # writer.writerow(["timestamp", "user", "app"] + [f"metric_{i}" for i in range(1, 10)])
        
        for _ in range(rows_per_day):
            timestamp = current_date + timedelta(
                hours=random.randint(0, 23),
                minutes=random.randint(0, 59),
                seconds=random.randint(0, 59)
            )
            user = random.choice(users)
            app = random.choice(apps)
            metrics = [random.randint(1, 1000) for _ in range(9)]
            writer.writerow([timestamp.strftime("%Y-%m-%d %H:%M:%S"), user, app] + metrics)
    
    current_date += timedelta(days=1)

log_dir
