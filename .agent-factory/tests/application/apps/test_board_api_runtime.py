"""Board API runtime helper tests."""

from __future__ import annotations

import hashlib

from engine.apps.board_api.runtime import (
    board_url_file_path,
    read_board_url_port,
    reap_zombie_children,
    refresh_existing_board_url,
    remove_board_url_file,
    resolve_port,
    write_board_url_file,
)


def test_resolve_port_starts_from_project_hash_and_skips_used_ports() -> None:
    project_root = "/tmp/example-project"
    start = 9900
    end = 9903
    range_size = end - start + 1
    hash_int = int.from_bytes(hashlib.md5(project_root.encode()).digest()[:4], "big")
    first = start + (hash_int % range_size)
    second = start + ((hash_int % range_size) + 1) % range_size

    assert resolve_port(
        project_root,
        range_start=start,
        range_end=end,
        port_in_use=lambda port: port == first,
    ) == second


def test_resolve_port_raises_when_range_is_full() -> None:
    try:
        resolve_port(
            "/tmp/full",
            range_start=9900,
            range_end=9901,
            port_in_use=lambda _port: True,
        )
    except RuntimeError as exc:
        assert "9900~9901" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")


def test_write_and_remove_board_url_file(tmp_path) -> None:
    base = write_board_url_file(str(tmp_path), 9912)
    path = board_url_file_path(str(tmp_path))

    assert base == "http://127.0.0.1:9912"
    assert path.read_text(encoding="utf-8").splitlines() == [
        "http://127.0.0.1:9912/index.html",
        "http://127.0.0.1:9912/board.html",
        "http://127.0.0.1:9912/terminal.html",
    ]

    remove_board_url_file(str(tmp_path))

    assert not path.exists()


def test_read_and_refresh_existing_board_url(tmp_path) -> None:
    write_board_url_file(str(tmp_path), 9912)

    assert read_board_url_port(str(tmp_path)) == 9912

    refresh_existing_board_url(str(tmp_path), 9913)

    assert read_board_url_port(str(tmp_path)) == 9913
    assert board_url_file_path(str(tmp_path)).read_text(encoding="utf-8").splitlines() == [
        "http://127.0.0.1:9913/index.html",
        "http://127.0.0.1:9913/board.html",
        "http://127.0.0.1:9913/terminal.html",
    ]


def test_read_board_url_port_returns_none_for_missing_or_invalid_file(tmp_path) -> None:
    assert read_board_url_port(str(tmp_path)) is None

    path = board_url_file_path(str(tmp_path))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("://bad-url", encoding="utf-8")

    assert read_board_url_port(str(tmp_path)) is None


def test_reap_zombie_children_counts_until_no_child_status() -> None:
    calls = iter([(111, 0), (222, 0), (0, 0)])

    assert reap_zombie_children(waitpid=lambda _pid, _flags: next(calls)) == 2


def test_reap_zombie_children_treats_no_children_as_zero() -> None:
    def no_children(_pid: int, _flags: int) -> tuple[int, int]:
        raise ChildProcessError

    assert reap_zombie_children(waitpid=no_children) == 0
