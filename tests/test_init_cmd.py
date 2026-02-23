"""Tests for kanibako init / new commands."""

from __future__ import annotations


from kanibako.cli import _SUBCOMMANDS, build_parser
from kanibako.commands.init import run_init, run_new


# ---------------------------------------------------------------------------
# Parser tests
# ---------------------------------------------------------------------------

class TestInitParser:
    def test_init_parser(self):
        parser = build_parser()
        args = parser.parse_args(["init", "--local"])
        assert args.command == "init"
        assert args.local is True
        assert args.project is None

    def test_init_parser_with_project(self):
        parser = build_parser()
        args = parser.parse_args(["init", "--local", "-p", "/tmp/mydir"])
        assert args.command == "init"
        assert args.local is True
        assert args.project == "/tmp/mydir"

    def test_new_parser(self):
        parser = build_parser()
        args = parser.parse_args(["new", "--local", "/tmp/foo"])
        assert args.command == "new"
        assert args.local is True
        assert args.path == "/tmp/foo"

    def test_init_and_new_in_subcommands(self):
        assert "init" in _SUBCOMMANDS
        assert "new" in _SUBCOMMANDS


# ---------------------------------------------------------------------------
# TestRunInit
# ---------------------------------------------------------------------------

class TestRunInit:
    def test_init_local_creates_project(
        self, config_file, credentials_dir, project_dir, capsys,
    ):
        parser = build_parser()
        args = parser.parse_args(["init", "--local", "-p", str(project_dir)])
        rc = run_init(args)

        assert rc == 0
        resolved = project_dir.resolve()
        assert (resolved / ".kanibako").is_dir()
        assert (resolved / ".kanibako" / "shell").is_dir()
        assert (resolved / "vault" / "share-ro").is_dir()
        assert (resolved / "vault" / "share-rw").is_dir()

    def test_init_local_writes_gitignore(
        self, config_file, credentials_dir, project_dir, capsys,
    ):
        parser = build_parser()
        args = parser.parse_args(["init", "--local", "-p", str(project_dir)])
        run_init(args)

        gitignore = project_dir.resolve() / ".gitignore"
        assert gitignore.is_file()
        content = gitignore.read_text()
        assert ".kanibako/" in content

    def test_init_without_local_fails(self, config_file, project_dir, capsys):
        parser = build_parser()
        args = parser.parse_args(["init", "-p", str(project_dir)])
        rc = run_init(args)

        assert rc == 1
        captured = capsys.readouterr()
        assert "specify a project mode" in captured.err

    def test_init_reinit_says_already(
        self, config_file, credentials_dir, project_dir, capsys,
    ):
        parser = build_parser()
        args = parser.parse_args(["init", "--local", "-p", str(project_dir)])
        run_init(args)

        # Clear captured output, then reinit
        capsys.readouterr()
        rc = run_init(args)

        assert rc == 0
        captured = capsys.readouterr()
        assert "already initialized" in captured.out


# ---------------------------------------------------------------------------
# TestRunNew
# ---------------------------------------------------------------------------

class TestRunNew:
    def test_new_local_creates_directory_and_project(
        self, config_file, credentials_dir, tmp_home, capsys,
    ):
        target = tmp_home / "brand-new-project"
        parser = build_parser()
        args = parser.parse_args(["new", "--local", str(target)])
        rc = run_new(args)

        assert rc == 0
        resolved = target.resolve()
        assert resolved.is_dir()
        assert (resolved / ".kanibako").is_dir()
        assert (resolved / ".kanibako" / "shell").is_dir()

    def test_new_local_writes_gitignore(
        self, config_file, credentials_dir, tmp_home, capsys,
    ):
        target = tmp_home / "new-proj-gi"
        parser = build_parser()
        args = parser.parse_args(["new", "--local", str(target)])
        run_new(args)

        gitignore = target.resolve() / ".gitignore"
        assert gitignore.is_file()
        content = gitignore.read_text()
        assert ".kanibako/" in content

    def test_new_without_local_fails(self, config_file, tmp_home, capsys):
        target = tmp_home / "should-not-exist"
        parser = build_parser()
        args = parser.parse_args(["new", str(target)])
        rc = run_new(args)

        assert rc == 1
        captured = capsys.readouterr()
        assert "specify a project mode" in captured.err
        assert not target.exists()

    def test_new_existing_path_fails(
        self, config_file, tmp_home, capsys,
    ):
        target = tmp_home / "already-here"
        target.mkdir()
        parser = build_parser()
        args = parser.parse_args(["new", "--local", str(target)])
        rc = run_new(args)

        assert rc == 1
        captured = capsys.readouterr()
        assert "already exists" in captured.err


class TestInitNoVault:
    """Tests for --no-vault flag on init / new."""

    def test_init_no_vault_skips_vault_dirs(
        self, config_file, tmp_home, credentials_dir, capsys,
    ):
        project = tmp_home / "novault-project"
        project.mkdir()
        parser = build_parser()
        args = parser.parse_args(["init", "--local", "-p", str(project), "--no-vault"])
        rc = run_init(args)

        assert rc == 0
        assert (project / ".kanibako").is_dir()
        assert not (project / "vault").exists()

    def test_new_no_vault_skips_vault_dirs(
        self, config_file, tmp_home, credentials_dir, capsys,
    ):
        target = tmp_home / "novault-new"
        parser = build_parser()
        args = parser.parse_args(["new", "--local", str(target), "--no-vault"])
        rc = run_new(args)

        assert rc == 0
        assert (target / ".kanibako").is_dir()
        assert not (target / "vault").exists()

    def test_init_with_vault_creates_vault_dirs(
        self, config_file, tmp_home, credentials_dir, capsys,
    ):
        project = tmp_home / "vault-project"
        project.mkdir()
        parser = build_parser()
        args = parser.parse_args(["init", "--local", "-p", str(project)])
        rc = run_init(args)

        assert rc == 0
        assert (project / "vault" / "share-ro").is_dir()
        assert (project / "vault" / "share-rw").is_dir()


class TestInitDistinctAuth:
    """Tests for --distinct-auth flag on init / new."""

    def test_init_distinct_auth_skips_creds(
        self, config_file, tmp_home, credentials_dir, capsys,
    ):
        project = tmp_home / "distinct-project"
        project.mkdir()
        parser = build_parser()
        args = parser.parse_args(["init", "--local", "-p", str(project), "--distinct-auth"])
        rc = run_init(args)

        assert rc == 0
        shell = project / ".kanibako" / "shell"
        assert shell.is_dir()
        # Credentials should NOT have been copied from host.
        assert not (shell / ".claude" / ".credentials.json").exists()

    def test_init_distinct_auth_sets_meta(
        self, config_file, tmp_home, credentials_dir, capsys,
    ):
        from kanibako.config import read_project_meta
        project = tmp_home / "distinct-meta"
        project.mkdir()
        parser = build_parser()
        args = parser.parse_args(["init", "--local", "-p", str(project), "--distinct-auth"])
        run_init(args)

        meta = read_project_meta(project / ".kanibako" / "project.toml")
        assert meta is not None
        assert meta["auth"] == "distinct"

    def test_parser_accepts_distinct_auth(self):
        parser = build_parser()
        args = parser.parse_args(["init", "--local", "--distinct-auth"])
        assert args.distinct_auth is True

    def test_new_distinct_auth(
        self, config_file, tmp_home, credentials_dir, capsys,
    ):
        target = tmp_home / "distinct-new"
        parser = build_parser()
        args = parser.parse_args(["new", "--local", str(target), "--distinct-auth"])
        rc = run_new(args)

        assert rc == 0
        shell = target / ".kanibako" / "shell"
        assert shell.is_dir()
        assert not (shell / ".claude" / ".credentials.json").exists()
