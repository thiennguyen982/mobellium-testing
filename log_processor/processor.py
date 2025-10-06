import csv
import sys
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict
import os


class LogProcessor:
    def __init__(self, logs_dir="logs"):
        self.logs_dir = Path(logs_dir)

    @staticmethod
    def parse_datetime(dt_str):
        return datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")

    @staticmethod
    def get_time_bucket(dt, granularity):
        if granularity == "30m":
            minutes = (dt.minute // 30) * 30
            return dt.replace(minute=minutes, second=0, microsecond=0)
        elif granularity == "1day":
            return dt.replace(hour=0, minute=0, second=0, microsecond=0)
        raise ValueError(f"Invalid granularity: {granularity}")

    def get_log_files(self, from_dt, to_dt):
        files = []
        current_date = from_dt.date()
        while current_date <= to_dt.date():
            f = self.logs_dir / f"{current_date}.log.csv"
            if f.exists():
                files.append(f)
            current_date += timedelta(days=1)
        return files

    @staticmethod
    def parse_dimensions(dimensions_str):
        return [d.strip() for d in dimensions_str.split(",")]

    @staticmethod
    def parse_filter_list(filter_str):
        if not filter_str:
            return None
        return set(v.strip() for v in filter_str.split(","))

    @staticmethod
    def flush_user_data(user_data, dimensions, writer):
        if not user_data:
            return

        sorted_items = sorted(user_data.items())
        for key, metrics in sorted_items:
            time_bucket = key[0]
            timestamp_str = time_bucket.strftime("%Y-%m-%d %H:%M:%S")

            row = [timestamp_str]
            for i, dim in enumerate(dimensions):
                row.append(key[i + 1])
            row.extend(metrics)

            writer.writerow(row)

        user_data.clear()

    @staticmethod
    def _write_header(writer, dimensions):
        header = ["timestamp"] + dimensions + [f"metric_{i}" for i in range(1, 10)]
        writer.writerow(header)

    @staticmethod
    def user_to_num(user):
        try:
            return int(user.replace("user", ""))
        except (ValueError, AttributeError):
            return float("inf")

    def find_user_start_position(self, file_handle, target_user):
        file_handle.seek(0, 2)
        file_size = file_handle.tell()
        if file_size == 0:
            return None

        target_num = self.user_to_num(target_user)
        left, right = 0, file_size
        best_pos = None

        while left < right:
            mid = (left + right) // 2
            file_handle.seek(mid)
            if mid > 0:
                file_handle.readline()

            pos = file_handle.tell()
            if pos >= file_size:
                right = mid
                continue

            line = file_handle.readline()
            if not line:
                right = mid
                continue

            parts = line.strip().split(",")
            if len(parts) < 2:
                right = mid
                continue

            current_user = parts[1]
            current_num = self.user_to_num(current_user)

            if current_num < target_num:
                left = mid + 1
            elif current_num > target_num:
                right = mid
            else:
                best_pos = pos
                right = mid

        if best_pos is not None:
            file_handle.seek(max(0, best_pos - 10000))
            if best_pos > 0:
                file_handle.readline()
            while True:
                pos = file_handle.tell()
                line = file_handle.readline()
                if not line:
                    break
                parts = line.strip().split(",")
                if len(parts) >= 2 and parts[1] == target_user:
                    file_handle.seek(pos)
                    return pos
                if len(parts) >= 2 and self.user_to_num(parts[1]) > target_num:
                    break
        return best_pos

    def process_user_data(
        self,
        f,
        target_user,
        from_dt,
        to_dt,
        app_filter,
        granularity,
        dimensions,
        user_data,
    ):
        reader = csv.reader(f)
        rows_processed = 0
        for row in reader:
            if len(row) < 12:
                continue
            timestamp_str, user, app = row[0], row[1], row[2]
            metrics = [int(row[i]) for i in range(3, 12)]

            if user != target_user:
                break

            rows_processed += 1
            row_dt = self.parse_datetime(timestamp_str)
            if row_dt < from_dt or row_dt >= to_dt:
                continue
            if app_filter and app not in app_filter:
                continue

            time_bucket = self.get_time_bucket(row_dt, granularity)
            key_parts = [time_bucket]
            for dim in dimensions:
                if dim == "user":
                    key_parts.append(user)
                elif dim == "app":
                    key_parts.append(app)
            key = tuple(key_parts)

            for i in range(9):
                user_data[key][i] += metrics[i]

        return rows_processed

    def _process_logs_with_user_filter(
        self,
        log_files,
        from_dt,
        to_dt,
        user_filter,
        app_filter,
        granularity,
        dimensions,
        writer,
    ):
        sorted_users = sorted(user_filter, key=self.user_to_num)
        for target_user in sorted_users:
            user_data = defaultdict(lambda: [0] * 9)
            for log_file in log_files:
                with open(log_file, "r") as f:
                    start_pos = self.find_user_start_position(f, target_user)
                    if start_pos is not None:
                        self.process_user_data(
                            f,
                            target_user,
                            from_dt,
                            to_dt,
                            app_filter,
                            granularity,
                            dimensions,
                            user_data,
                        )
            self.flush_user_data(user_data, dimensions, writer)

    def _process_logs_with_user_dimension(
        self, log_files, from_dt, to_dt, app_filter, granularity, dimensions, writer
    ):
        current_user = None
        user_data = defaultdict(lambda: [0] * 9)
        for log_file in log_files:
            with open(log_file, "r") as f:
                reader = csv.reader(f)
                for row in reader:
                    if len(row) < 12:
                        continue
                    timestamp_str, user, app = row[0], row[1], row[2]
                    metrics = [int(row[i]) for i in range(3, 12)]

                    if current_user is not None and user != current_user:
                        self.flush_user_data(user_data, dimensions, writer)
                    current_user = user

                    row_dt = self.parse_datetime(timestamp_str)
                    if row_dt < from_dt or row_dt >= to_dt:
                        continue
                    if app_filter and app not in app_filter:
                        continue

                    time_bucket = self.get_time_bucket(row_dt, granularity)
                    key_parts = [time_bucket]
                    for dim in dimensions:
                        if dim == "user":
                            key_parts.append(user)
                        elif dim == "app":
                            key_parts.append(app)
                    key = tuple(key_parts)

                    for i in range(9):
                        user_data[key][i] += metrics[i]
        self.flush_user_data(user_data, dimensions, writer)

    def _process_logs_without_user_dimension(
        self,
        log_files,
        from_dt,
        to_dt,
        user_filter,
        app_filter,
        granularity,
        dimensions,
        writer,
    ):
        aggregated = defaultdict(lambda: [0] * 9)
        for log_file in log_files:
            with open(log_file, "r") as f:
                reader = csv.reader(f)
                for row in reader:
                    if len(row) < 12:
                        continue
                    timestamp_str, user, app = row[0], row[1], row[2]
                    metrics = [int(row[i]) for i in range(3, 12)]

                    row_dt = self.parse_datetime(timestamp_str)
                    if row_dt < from_dt or row_dt >= to_dt:
                        continue
                    if user_filter and user not in user_filter:
                        continue
                    if app_filter and app not in app_filter:
                        continue

                    time_bucket = self.get_time_bucket(row_dt, granularity)
                    key_parts = [time_bucket]
                    for dim in dimensions:
                        if dim == "app":
                            key_parts.append(app)
                    key = tuple(key_parts)

                    for i in range(9):
                        aggregated[key][i] += metrics[i]

        for key, metrics in sorted(aggregated.items()):
            time_bucket = key[0]
            timestamp_str = time_bucket.strftime("%Y-%m-%d %H:%M:%S")
            row = [timestamp_str]
            for i, dim in enumerate(dimensions):
                row.append(key[i + 1])
            row.extend(metrics)
            writer.writerow(row)

    def process_logs(
        self,
        from_dt,
        to_dt,
        user_filter,
        app_filter,
        granularity,
        dimensions,
        output_file=None,
    ):
        log_files = self.get_log_files(from_dt, to_dt)
        has_user_dimension = "user" in dimensions

        if output_file:
            os.makedirs(os.path.dirname(output_file), exist_ok=True)

        f_out = open(output_file, "w", newline="") if output_file else None
        writer = csv.writer(f_out or sys.stdout)

        self._write_header(writer, dimensions)

        if user_filter:
            self._process_logs_with_user_filter(
                log_files,
                from_dt,
                to_dt,
                user_filter,
                app_filter,
                granularity,
                dimensions,
                writer,
            )
        elif has_user_dimension:
            self._process_logs_with_user_dimension(
                log_files, from_dt, to_dt, app_filter, granularity, dimensions, writer
            )
        else:
            self._process_logs_without_user_dimension(
                log_files,
                from_dt,
                to_dt,
                user_filter,
                app_filter,
                granularity,
                dimensions,
                writer,
            )

        if f_out:
            f_out.close()
