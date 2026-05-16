from pathlib import Path

from core.safety import (
    BACKUP_DIR_NAME,
    MAX_BACKUPS,
    MAX_OUTPUT_SIZE,
    MAX_WRITE_SIZE,
    backup_file,
    check_write_safety,
    get_tool_timeout,
    sanitize_env,
    truncate_output,
)


class TestSanitizeEnv:
    def test_sensitive_var_stripped(self):
        env = {"OPENROUTER_API_KEY": "sk-xxx", "HOME": "/home/user"}
        cleaned = sanitize_env(env)
        assert "OPENROUTER_API_KEY" not in cleaned
        assert cleaned["HOME"] == "/home/user"

    def test_multiple_sensitive_patterns(self):
        env = {
            "AWS_SECRET_ACCESS_KEY": "abc",
            "DATABASE_URL": "postgres://...",
            "PATH": "/usr/bin",
        }
        cleaned = sanitize_env(env)
        assert "AWS_SECRET_ACCESS_KEY" not in cleaned
        assert "DATABASE_URL" not in cleaned
        assert cleaned["PATH"] == "/usr/bin"

    def test_case_insensitivity(self):
        env = {"openrouter_api_key": "sk-xxx", "brave_token": "tok"}
        cleaned = sanitize_env(env)
        assert "openrouter_api_key" not in cleaned
        assert "brave_token" not in cleaned

    def test_safe_vars_kept(self):
        env = {"PATH": "/usr/bin", "HOME": "/home", "SHELL": "/bin/bash"}
        cleaned = sanitize_env(env)
        assert cleaned == env

    def test_empty_env(self):
        cleaned = sanitize_env({})
        assert cleaned == {}

    def test_allow_patterns_override(self):
        env = {"MY_SECRET": "s3kr3t", "SAFE_VAR": "ok"}
        cleaned = sanitize_env(env, allow_patterns=["MY_SECRET"])
        assert "MY_SECRET" in cleaned
        assert cleaned["SAFE_VAR"] == "ok"

    def test_allow_patterns_case_insensitive(self):
        env = {"my_secret": "val"}
        cleaned = sanitize_env(env, allow_patterns=["MY_SECRET"])
        assert "my_secret" in cleaned

    def test_non_matching_allow_pattern(self):
        env = {"OPENROUTER_KEY": "sk-xxx"}
        cleaned = sanitize_env(env, allow_patterns=["OTHER_KEY"])
        assert "OPENROUTER_KEY" not in cleaned

    def test_pattern_matching_edge_cases(self):
        env = {"_KEY": "x", "SECRET": "y", "MY_TOKEN": "z"}
        cleaned = sanitize_env(env)
        assert "_KEY" not in cleaned  # matches *_KEY
        assert "SECRET" in cleaned  # doesn't match *_SECRET (no underscore prefix)
        assert "MY_TOKEN" not in cleaned  # matches *_TOKEN

    def test_unrelated_vars_unchanged(self):
        env = {"FOO": "bar", "ZOO": "zar"}
        cleaned = sanitize_env(env)
        assert cleaned == env


class TestCheckWriteSafety:
    def test_content_exceeds_max_size(self):
        content = "x" * (MAX_WRITE_SIZE + 1)
        target = Path("test.txt")
        err = check_write_safety(content, target)
        expected = f"Error: write rejected — content is {len(content.encode('utf-8')):,} bytes, max is {MAX_WRITE_SIZE:,}"
        assert err == expected

    def test_content_exactly_max_size_passes(self):
        content = "x" * MAX_WRITE_SIZE
        target = Path("test.txt")
        err = check_write_safety(content, target)
        assert err is None

    def test_binary_extension_blocked_when_exists(self, tmp_path):
        content = "hello"
        for ext in [".exe", ".dll", ".png", ".zip", ".pdf"]:
            target = tmp_path / f"file{ext}"
            target.write_bytes(b"\x00binary")
            err = check_write_safety(content, target)
            assert err is not None, f"Expected block for {ext}"
            assert "refusing to overwrite binary file" in err

    def test_binary_extension_case_insensitive(self, tmp_path):
        content = "data"
        target = tmp_path / "file.EXE"
        target.write_bytes(b"\x00binary")
        err = check_write_safety(content, target)
        assert err is not None
        assert "refusing to overwrite binary file file.EXE" in err

    def test_normal_file_passes(self):
        content = "normal content"
        target = Path("readme.txt")
        err = check_write_safety(content, target)
        assert err is None

    def test_binary_extension_non_existent_file_not_blocked(self):
        content = "data"
        target = Path("file.exe")
        assert not target.exists()
        err = check_write_safety(content, target)
        assert err is None  # no existing file to worry about

    def test_binary_extension_existing_file_blocked(self, tmp_path):
        content = "data"
        target = tmp_path / "file.exe"
        target.write_text("old", encoding="utf-8")
        err = check_write_safety(content, target)
        assert err is not None

    def test_non_binary_extension_with_existing_file_passes(self, tmp_path):
        content = "new data"
        target = tmp_path / "file.txt"
        target.write_text("old", encoding="utf-8")
        err = check_write_safety(content, target)
        assert err is None

    def test_empty_content_passes(self):
        content = ""
        target = Path("empty.txt")
        err = check_write_safety(content, target)
        assert err is None


class TestBackupFile:
    def test_existing_file_backed_up(self, tmp_path):
        work_dir = tmp_path / "project"
        work_dir.mkdir()
        src = work_dir / "file.txt"
        src.write_text("original", encoding="utf-8")
        backup_path = backup_file(src, work_dir)
        assert backup_path is not None
        backup_dir = work_dir / BACKUP_DIR_NAME
        assert backup_dir.exists()
        assert backup_path.exists()
        assert backup_path.read_text(encoding="utf-8") == "original"

    def test_nonexistent_file_returns_none(self, tmp_path):
        work_dir = tmp_path / "project"
        work_dir.mkdir()
        src = work_dir / "missing.txt"
        assert not src.exists()
        result = backup_file(src, work_dir)
        assert result is None

    def test_backup_naming_contains_timestamp_and_path(self, tmp_path):
        work_dir = tmp_path / "project"
        work_dir.mkdir()
        src = work_dir / "src" / "main.py"
        src.parent.mkdir()
        src.write_text("code", encoding="utf-8")
        backup_path = backup_file(src, work_dir)
        assert backup_path is not None
        name = backup_path.name
        # Should contain timestamp like 20231028_120000 and path name
        assert name.count("__") >= 2
        # The path should be encoded: "src__main.py"
        assert "src__main.py" in name or name.endswith("src__main.py")

    def test_backup_creates_backup_dir(self, tmp_path):
        work_dir = tmp_path / "project"
        work_dir.mkdir()
        src = work_dir / "file.txt"
        src.write_text("data", encoding="utf-8")
        backup_path = backup_file(src, work_dir)
        assert backup_path is not None
        backup_dir = work_dir / BACKUP_DIR_NAME
        assert backup_dir.is_dir()

    def test_backup_with_subdirs(self, tmp_path):
        work_dir = tmp_path / "project"
        work_dir.mkdir()
        src = work_dir / "a" / "b" / "c.txt"
        src.parent.mkdir(parents=True)
        src.write_text("deep", encoding="utf-8")
        backup_path = backup_file(src, work_dir)
        assert backup_path is not None
        # The safe_name should replace separators with "__"
        assert "a__b__c.txt" in backup_path.name or backup_path.name.endswith("a__b__c.txt")

    def test_pruning_old_backups(self, tmp_path):
        work_dir = tmp_path / "project"
        work_dir.mkdir()
        src = work_dir / "file.txt"
        src.write_text("data", encoding="utf-8")
        backup_dir = work_dir / BACKUP_DIR_NAME
        backup_dir.mkdir(parents=True)

        import os

        for i in range(MAX_BACKUPS + 10):
            old_backup = backup_dir / f"20200101_000000__old_{i}.txt"
            old_backup.write_text("old", encoding="utf-8")
            old_time = 946684800 + i
            os.utime(old_backup, (old_time, old_time))

        # Now call backup_file — it should prune
        backup_path = backup_file(src, work_dir)
        assert backup_path is not None

        # The backup dir should now have at most MAX_BACKUPS + 1 (the new one)
        remaining = list(backup_dir.iterdir())
        assert len(remaining) <= MAX_BACKUPS + 1  # the pruning may remove extras

        # The newest file should be the one we just created
        sorted_backups = sorted(remaining, key=lambda p: p.stat().st_mtime)
        assert sorted_backups[-1] == backup_path

    def test_pruning_removes_oldest_first(self, tmp_path):
        work_dir = tmp_path / "project"
        work_dir.mkdir()
        src = work_dir / "f.txt"
        src.write_text("data", encoding="utf-8")
        backup_dir = work_dir / BACKUP_DIR_NAME
        backup_dir.mkdir(parents=True)

        # Create MAX_BACKUPS + 5 backups with varying mtimes
        import os

        for i in range(MAX_BACKUPS + 5):
            bp = backup_dir / f"b_{i}.bak"
            bp.write_text("x", encoding="utf-8")
            # mtime = i days ago (simulate different ages)
            os.utime(bp, (1000 + i, 1000 + i))

        backup_path = backup_file(src, work_dir)
        remaining = sorted(backup_dir.iterdir(), key=lambda p: p.stat().st_mtime)
        # The newest remaining should be the new backup
        assert remaining[-1] == backup_path
        # Total count should be <= MAX_BACKUPS + 1
        assert len(remaining) <= MAX_BACKUPS + 1

    def test_pruning_handles_pruning_error_gracefully(self, tmp_path):
        """If a file can't be deleted, prune continues."""
        work_dir = tmp_path / "project"
        work_dir.mkdir()
        src = work_dir / "file.txt"
        src.write_text("data", encoding="utf-8")
        backup_dir = work_dir / BACKUP_DIR_NAME
        backup_dir.mkdir(parents=True)

        import os
        import stat

        for i in range(MAX_BACKUPS + 5):
            bp = backup_dir / f"b_{i}.bak"
            bp.write_text("x", encoding="utf-8")
        make_readonly = backup_dir / "b_0.bak"
        os.chmod(make_readonly, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)

        backup_path = backup_file(src, work_dir)
        assert backup_path is not None
        # Should still have at most MAX_BACKUPS+1 (the new one)
        remaining = list(backup_dir.iterdir())
        assert len(remaining) <= MAX_BACKUPS + 1

    def test_backup_file_inside_backup_dir(self, tmp_path):
        """Edge: file already inside .model-chat-backups should not cause issues."""
        work_dir = tmp_path / "project"
        work_dir.mkdir()
        backup_dir = work_dir / BACKUP_DIR_NAME
        backup_dir.mkdir(parents=True)
        src = backup_dir / "already_backed.txt"
        src.write_text("inside", encoding="utf-8")
        result = backup_file(src, work_dir)
        # Should still work, naming will include backup dir in path
        assert result is not None
        assert result.exists()

    def test_backup_from_outside_work_dir(self, tmp_path):
        """File not under work_dir: backup uses just filename."""
        work_dir = tmp_path / "project"
        work_dir.mkdir()
        outside = tmp_path / "outside.txt"
        outside.write_text("data", encoding="utf-8")
        result = backup_file(outside, work_dir)
        assert result is not None
        # Name should be just "outside.txt" (no path separators)
        assert "outside.txt" in result.name


class TestTruncateOutput:
    def test_under_limit_unchanged(self):
        output = "short text"
        assert truncate_output(output) == output

    def test_at_limit_unchanged(self):
        output = "a" * MAX_OUTPUT_SIZE
        assert truncate_output(output) == output

    def test_exceeds_limit_truncated(self):
        output = "a" * (MAX_OUTPUT_SIZE + 100)
        truncated = truncate_output(output)
        assert len(truncated) < len(output)
        assert truncated.endswith(f"\n\n[truncated — output exceeded {MAX_OUTPUT_SIZE} characters]")
        # The truncated part should be exactly MAX_OUTPUT_SIZE + the suffix length
        suffix = f"\n\n[truncated — output exceeded {MAX_OUTPUT_SIZE} characters]"
        assert len(truncated) == MAX_OUTPUT_SIZE + len(suffix)

    def test_custom_max_size(self):
        output = "a" * 100
        truncated = truncate_output(output, max_size=50)
        assert len(truncated) <= 50 + len(f"\n\n[truncated — output exceeded {50} characters]")

    def test_exact_custom_boundary(self):
        output = "a" * 50
        truncated = truncate_output(output, max_size=50)
        assert truncated == output

    def test_empty_output(self):
        assert truncate_output("") == ""

    def test_newlines_preserved_in_truncation(self):
        output = "line1\nline2\n" * (MAX_OUTPUT_SIZE // 10 + 1)
        truncated = truncate_output(output)
        assert "\n" in truncated
        assert truncated.endswith(f"\n\n[truncated — output exceeded {MAX_OUTPUT_SIZE} characters]")


class TestGetToolTimeout:
    def test_known_tools_return_configured(self):
        known_timeouts = {
            "shell": 120,
            "web_search": 15,
            "read_file": 10,
            "write_file": 10,
            "edit_file": 10,
            "glob": 10,
            "grep": 30,
        }
        for tool, expected in known_timeouts.items():
            assert get_tool_timeout(tool) == expected

    def test_unknown_tool_returns_default(self):
        assert get_tool_timeout("unknown_tool") == 30

    def test_case_sensitive(self):
        # Should be case-sensitive
        assert get_tool_timeout("Shell") == 30
        assert get_tool_timeout("SHELL") == 30

    def test_empty_string(self):
        assert get_tool_timeout("") == 30

    def test_none_tool_name_returns_default(self):
        assert get_tool_timeout(None) == 30
