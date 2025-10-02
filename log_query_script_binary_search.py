#!/usr/bin/env python3
"""
Efficiently query and aggregate large CSV log files.
Optimized to leverage sorted-by-user property for memory efficiency.
"""

import argparse
import csv
import sys
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict


def parse_datetime(dt_str):
    """Parse datetime string in format 'YYYY-MM-DD HH:MM:SS'"""
    return datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")


def get_time_bucket(dt, granularity):
    """
    Get the start of the time bucket for a given datetime.
    granularity: '30m' or '1day'
    """
    if granularity == '30m':
        # Round down to nearest 30 minutes
        minutes = (dt.minute // 30) * 30
        return dt.replace(minute=minutes, second=0, microsecond=0)
    elif granularity == '1day':
        # Round down to start of day
        return dt.replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        raise ValueError(f"Invalid granularity: {granularity}")


def get_log_files(from_dt, to_dt, logs_dir="logs"):
    """
    Get list of log files needed for the date range.
    Returns sorted list of Path objects.
    """
    logs_path = Path(logs_dir)
    if not logs_path.exists():
        return []
    
    files = []
    current_date = from_dt.date()
    end_date = to_dt.date()
    
    while current_date <= end_date:
        log_file = logs_path / f"{current_date}.log.csv"
        if log_file.exists():
            files.append(log_file)
        current_date += timedelta(days=1)
    
    return files


def parse_dimensions(dimensions_str):
    """Parse dimensions string into list."""
    return [d.strip() for d in dimensions_str.split(',')]


def parse_filter_list(filter_str):
    """Parse comma-separated filter values."""
    if not filter_str:
        return None
    return set(v.strip() for v in filter_str.split(','))


def flush_user_data(user_data, dimensions, writer):
    """
    Output aggregated data for completed user and clear memory.
    """
    if not user_data:
        return
    
    # Sort by key (time_bucket and other dimensions)
    sorted_items = sorted(user_data.items())
    
    for key, metrics in sorted_items:
        time_bucket = key[0]
        timestamp_str = time_bucket.strftime("%Y-%m-%d %H:%M:%S")
        
        row = [timestamp_str]
        
        # Add dimension values
        for i, dim in enumerate(dimensions):
            row.append(key[i + 1])
        
        # Add metrics
        row.extend(metrics)
        
        writer.writerow(row)
    
    # Clear the data
    user_data.clear()


def user_to_num(user):
    """Convert user string to number for comparison."""
    try:
        return int(user.replace('user', ''))
    except (ValueError, AttributeError):
        return float('inf')


def find_user_start_position(file_handle, target_user):
    """
    Use binary search to find the starting position for target_user.
    Returns file position to start reading from, or None if user not in range.
    """
    file_handle.seek(0, 2)  # Seek to end
    file_size = file_handle.tell()
    
    if file_size == 0:
        return None
    
    target_num = user_to_num(target_user)
    
    # Binary search on file positions
    left, right = 0, file_size
    best_pos = None
    
    while left < right:
        mid = (left + right) // 2
        file_handle.seek(mid)
        
        # Read to next newline to get a complete row
        if mid > 0:
            file_handle.readline()  # Skip partial line
        
        pos = file_handle.tell()
        if pos >= file_size:
            right = mid
            continue
        
        line = file_handle.readline()
        if not line:
            right = mid
            continue
        
        try:
            parts = line.strip().split(',')
            if len(parts) < 2:
                right = mid
                continue
            
            current_user = parts[1]
            current_num = user_to_num(current_user)
            
            if current_num < target_num:
                left = mid + 1
            elif current_num > target_num:
                right = mid
            else:
                # Found the user, but we need the FIRST occurrence
                # Move left to find earlier occurrences
                best_pos = pos
                right = mid
        except (IndexError, ValueError):
            right = mid
    
    # If we found the user, scan back to find the very first occurrence
    if best_pos is not None:
        file_handle.seek(max(0, best_pos - 10000))  # Go back a bit
        if best_pos > 0:
            file_handle.readline()  # Skip partial line
        
        # Scan forward to find first occurrence of target_user
        while True:
            pos = file_handle.tell()
            line = file_handle.readline()
            if not line:
                break
            try:
                parts = line.strip().split(',')
                if len(parts) >= 2 and parts[1] == target_user:
                    file_handle.seek(pos)
                    return pos
                current_num = user_to_num(parts[1])
                if current_num > target_num:
                    # Passed the target user
                    break
            except (IndexError, ValueError):
                continue
    
    return best_pos


def process_user_data(f, target_user, from_dt, to_dt, app_filter, granularity, dimensions, user_data):
    """
    Process all rows for a specific user starting from current file position.
    Returns when we encounter a different user or EOF.
    """
    reader = csv.reader(f)
    rows_processed = 0
    
    for row in reader:
        if len(row) < 12:
            continue
        
        try:
            timestamp_str = row[0]
            user = row[1]
            app = row[2]
            metrics = [int(row[i]) for i in range(3, 12)]
            
            # If we've moved to a different user, we're done
            if user != target_user:
                break
            
            rows_processed += 1
            
            # Parse timestamp
            row_dt = parse_datetime(timestamp_str)
            
            # Apply datetime filter
            if row_dt < from_dt or row_dt >= to_dt:
                continue
            
            # Apply app filter
            if app_filter and app not in app_filter:
                continue
            
            # Get time bucket
            time_bucket = get_time_bucket(row_dt, granularity)
            
            # Create aggregation key based on dimensions
            key_parts = [time_bucket]
            for dim in dimensions:
                if dim == 'user':
                    key_parts.append(user)
                elif dim == 'app':
                    key_parts.append(app)
            
            key = tuple(key_parts)
            
            # Aggregate metrics
            for i in range(9):
                user_data[key][i] += metrics[i]
        
        except (ValueError, IndexError):
            continue
    
    return rows_processed


def process_logs_optimized(from_dt, to_dt, user_filter, app_filter, granularity, dimensions, logs_dir="logs", output_file=None):
    """
    Process log files with memory-efficient streaming when user is in dimensions.
    Leverages sorted-by-user property for both memory efficiency and early termination.
    Uses binary search to jump directly to each filtered user.
    """
    log_files = get_log_files(from_dt, to_dt, logs_dir)
    has_user_dimension = 'user' in dimensions
    
    # Setup output writer
    if output_file:
        f_out = open(output_file, 'w', newline='')
        writer = csv.writer(f_out)
    else:
        f_out = None
        writer = csv.writer(sys.stdout)
    
    # Print header
    header = ['timestamp'] + dimensions + [f'metric_{i}' for i in range(1, 10)]
    writer.writerow(header)
    
    if user_filter:
        # Optimized path: binary search to each filtered user
        # Works regardless of whether 'user' is in dimensions
        # Sort users to process them in order
        sorted_users = sorted(user_filter, key=user_to_num)
        
        for target_user in sorted_users:
            user_data = defaultdict(lambda: [0] * 9)
            
            for log_file in log_files:
                with open(log_file, 'r') as f:
                    # Binary search to find this user's starting position
                    start_pos = find_user_start_position(f, target_user)
                    
                    if start_pos is not None:
                        # Process all rows for this user
                        process_user_data(f, target_user, from_dt, to_dt, 
                                        app_filter, granularity, dimensions, user_data)
            
            # Flush this user's data
            flush_user_data(user_data, dimensions, writer)
    
    elif has_user_dimension:
        # User dimension but no filter: sequential scan with streaming
        current_user = None
        user_data = defaultdict(lambda: [0] * 9)
        for log_file in log_files:
            with open(log_file, 'r') as f:
                reader = csv.reader(f)
                
                for row in reader:
                    if len(row) < 12:
                        continue
                    
                    try:
                        timestamp_str = row[0]
                        user = row[1]
                        app = row[2]
                        metrics = [int(row[i]) for i in range(3, 12)]
                        
                        # Check if we've moved to a new user
                        if current_user is not None and user != current_user:
                            # Flush previous user's data
                            flush_user_data(user_data, dimensions, writer)
                        
                        current_user = user
                        
                        # Parse timestamp
                        row_dt = parse_datetime(timestamp_str)
                        
                        # Apply datetime filter
                        if row_dt < from_dt or row_dt >= to_dt:
                            continue
                        
                        # Apply app filter
                        if app_filter and app not in app_filter:
                            continue
                        
                        # Get time bucket
                        time_bucket = get_time_bucket(row_dt, granularity)
                        
                        # Create aggregation key based on dimensions
                        key_parts = [time_bucket]
                        for dim in dimensions:
                            if dim == 'user':
                                key_parts.append(user)
                            elif dim == 'app':
                                key_parts.append(app)
                        
                        key = tuple(key_parts)
                        
                        # Aggregate metrics
                        for i in range(9):
                            user_data[key][i] += metrics[i]
                    
                    except (ValueError, IndexError):
                        continue
        
        # Flush last user's data
        flush_user_data(user_data, dimensions, writer)
    
    else:
        # Non-optimized path: no user dimension, aggregate everything in memory
        aggregated = defaultdict(lambda: [0] * 9)
        
        for log_file in log_files:
            with open(log_file, 'r') as f:
                reader = csv.reader(f)
                
                for row in reader:
                    if len(row) < 12:
                        continue
                    
                    try:
                        timestamp_str = row[0]
                        user = row[1]
                        app = row[2]
                        metrics = [int(row[i]) for i in range(3, 12)]
                        
                        row_dt = parse_datetime(timestamp_str)
                        
                        if row_dt < from_dt or row_dt >= to_dt:
                            continue
                        
                        if user_filter and user not in user_filter:
                            continue
                        
                        if app_filter and app not in app_filter:
                            continue
                        
                        time_bucket = get_time_bucket(row_dt, granularity)
                        
                        key_parts = [time_bucket]
                        for dim in dimensions:
                            if dim == 'app':
                                key_parts.append(app)
                        
                        key = tuple(key_parts)
                        
                        for i in range(9):
                            aggregated[key][i] += metrics[i]
                    
                    except (ValueError, IndexError):
                        continue
        
        # Sort and output all results
        sorted_items = sorted(aggregated.items())
        for key, metrics in sorted_items:
            time_bucket = key[0]
            timestamp_str = time_bucket.strftime("%Y-%m-%d %H:%M:%S")
            
            row = [timestamp_str]
            for i, dim in enumerate(dimensions):
                row.append(key[i + 1])
            row.extend(metrics)
            
            writer.writerow(row)
    
    # Close output file if opened
    if f_out:
        f_out.close()


def main():
    parser = argparse.ArgumentParser(description='Query and aggregate log files')
    parser.add_argument('--from_datetime', required=True, help='Start datetime (YYYY-MM-DD HH:MM:SS)')
    parser.add_argument('--to_datetime', required=True, help='End datetime (YYYY-MM-DD HH:MM:SS)')
    parser.add_argument('--user', help='User ID(s), comma-separated')
    parser.add_argument('--app', help='App name(s), comma-separated')
    parser.add_argument('--granularity', required=True, choices=['30m', '1day'], help='Time granularity')
    parser.add_argument('--dimensions', required=True, help='Dimensions to group by (user, app, or user,app)')
    parser.add_argument('--logs_dir', default='logs', help='Directory containing log files')
    parser.add_argument('--output', help='Output file path (default: stdout)')
    
    args = parser.parse_args()
    
    try:
        # Parse arguments
        from_dt = parse_datetime(args.from_datetime)
        to_dt = parse_datetime(args.to_datetime)
        user_filter = parse_filter_list(args.user)
        app_filter = parse_filter_list(args.app)
        dimensions = parse_dimensions(args.dimensions)
        
        # Validate dimensions
        for dim in dimensions:
            if dim not in ['user', 'app']:
                print(f"Error: Invalid dimension '{dim}'", file=sys.stderr)
                sys.exit(1)
        
        # Process logs with optimization
        process_logs_optimized(from_dt, to_dt, user_filter, app_filter, 
                               args.granularity, dimensions, args.logs_dir, args.output)
    
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()