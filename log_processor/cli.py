#!/usr/bin/env python3
import argparse
import sys
from logs_processor.processor import LogProcessor


def main():
    parser = argparse.ArgumentParser(description="Query and aggregate log files")
    parser.add_argument("--from_datetime", required=True)
    parser.add_argument("--to_datetime", required=True)
    parser.add_argument("--user")
    parser.add_argument("--app")
    parser.add_argument("--granularity", required=True, choices=["30m", "1day"])
    parser.add_argument("--dimensions", required=True)
    parser.add_argument("--logs_dir", default="logs")
    parser.add_argument("--output")

    args = parser.parse_args()
    processor = LogProcessor(args.logs_dir)

    try:
        from_dt = processor.parse_datetime(args.from_datetime)
        to_dt = processor.parse_datetime(args.to_datetime)
        user_filter = processor.parse_filter_list(args.user)
        app_filter = processor.parse_filter_list(args.app)
        dimensions = processor.parse_dimensions(args.dimensions)

        for dim in dimensions:
            if dim not in ["user", "app"]:
                print(f"Error: Invalid dimension '{dim}'", file=sys.stderr)
                sys.exit(1)

        processor.process_logs(
            from_dt,
            to_dt,
            user_filter,
            app_filter,
            args.granularity,
            dimensions,
            args.output,
        )

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
