import csv
from datetime import datetime


class TestLogProcessor:
    def test_get_log_files_returns_only_within_date_range(
        self, processor, sample_log_dir
    ):
        """Should return files only within from_dt to to_dt (inclusive)"""
        from_dt = datetime(2025, 1, 1)
        to_dt = datetime(2025, 1, 1, 23, 59, 59)
        files = processor.get_log_files(from_dt, to_dt)
        assert len(files) == 1
        assert files[0].name == "2025-01-01.log.csv"

    def test_parse_dimensions_splits_and_strips(self, processor):
        """Should split dimension string by comma and trim spaces"""
        result = processor.parse_dimensions("user, app ,device")
        assert result == ["user", "app", "device"]

    def test_parse_filter_list_returns_set(self, processor):
        """Should return set of trimmed filter items"""
        result = processor.parse_filter_list("app1, app2, app3 ")
        assert result == {"app1", "app2", "app3"}

    def test_parse_filter_list_empty_string_returns_none(self, processor):
        """Empty string should return None (no filter)"""
        assert processor.parse_filter_list("") is None

    def test_user_to_num_extracts_integer_suffix(self, processor):
        """Should parse numerical part from user name correctly"""
        assert processor.user_to_num("user5") == 5
        assert processor.user_to_num("user0010") == 10

    def test_user_to_num_returns_inf_on_invalid_user(self, processor):
        """Should return float('inf') when user doesn't end in a number"""
        assert processor.user_to_num("userX") == float("inf")
        assert processor.user_to_num("") == float("inf")

    def test_find_user_start_position_finds_correct_start(
        self, processor, sample_log_dir
    ):
        """Should seek to the first occurrence of user1 in sorted CSV"""
        log_file = sample_log_dir / "2025-01-01.log.csv"
        with log_file.open("r") as f:
            pos = processor.find_user_start_position(f, "user1")
            assert pos is not None
            f.seek(pos)
            assert "user1" in f.readline()

    def test_process_logs_no_filters_aggregates_all_users_and_apps(
        self, processor, sample_log_dir
    ):
        """Should process and aggregate all rows without filters"""
        output_file = sample_log_dir / "all_output.csv"
        processor.process_logs(
            from_dt=datetime(2025, 1, 1, 0, 0, 0),
            to_dt=datetime(2025, 1, 2, 0, 0, 0),
            user_filter=None,
            app_filter=None,
            granularity="30m",
            dimensions=["user", "app"],
            output_file=str(output_file),
        )
        assert output_file.exists()

        rows = list(csv.reader(output_file.open()))
        assert rows[0] == ["timestamp", "user", "app"] + [
            f"metric_{i}" for i in range(1, 10)
        ]
        assert any("user1" in row for row in rows)
        assert any("app1" in row for row in rows)

    def test_process_logs_with_user_app_filter_filters_correctly(
        self, processor, sample_log_dir
    ):
        """Should only include data for user1 and app1"""
        output_file = sample_log_dir / "filtered_output.csv"
        processor.process_logs(
            from_dt=datetime(2025, 1, 1),
            to_dt=datetime(2025, 1, 2),
            user_filter={"user1"},
            app_filter={"app1"},
            granularity="30m",
            dimensions=["user", "app"],
            output_file=str(output_file),
        )

        rows = list(csv.reader(output_file.open()))
        assert all("user1" in row and "app1" in row for row in rows[1:])  # skip header

    def test_flush_user_data_writes_sorted_keys(self, processor, tmp_path):
        """Should write sorted time/dimension rows and clear user_data"""
        user_data = {
            (datetime(2025, 1, 1, 0, 0, 0), "user1", "app1"): list(range(1, 10)),
            (datetime(2025, 1, 1, 0, 30, 0), "user1", "app1"): [10] * 9,
        }
        output_file = tmp_path / "flush_test.csv"
        with output_file.open("w", newline="") as f:
            writer = csv.writer(f)
            processor._write_header(writer, ["user", "app"])
            processor.flush_user_data(user_data, ["user", "app"], writer)

        # Check header and both rows
        rows = list(csv.reader(output_file.open()))
        assert rows[0] == ["timestamp", "user", "app"] + [
            f"metric_{i}" for i in range(1, 10)
        ]
        assert len(rows) == 3  # 1 header + 2 rows
        assert rows[1][0] < rows[2][0]  # sorted by timestamp

    def test_flush_user_data_clears_dict(self, processor, tmp_path):
        """After flush, user_data dict should be empty"""
        user_data = {(datetime(2025, 1, 1), "u", "a"): [1] * 9}
        with (tmp_path / "dummy.csv").open("w", newline="") as f:
            writer = csv.writer(f)
            processor._write_header(writer, ["user", "app"])
            processor.flush_user_data(user_data, ["user", "app"], writer)
        assert len(user_data) == 0
