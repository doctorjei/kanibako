"""Extended tests for kanibako.paths: recovery paths, edge cases."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from kanibako.config import ClodboxConfig, load_config, write_global_config
from kanibako.errors import ConfigError, ProjectError
from kanibako.paths import load_std_paths, resolve_project


# ---------------------------------------------------------------------------
# Path recovery (initialize=True repairs missing dot_path / cfg_file)
# ---------------------------------------------------------------------------

class TestPathRecovery:
    def test_missing_dot_path_recovered(self, config_file, tmp_home, credentials_dir):
        config = load_config(config_file)
        std = load_std_paths(config)
        project_dir = str(tmp_home / "project")

        # First init
        proj = resolve_project(std, config, project_dir=project_dir, initialize=True)
        # Delete dot_path
        import shutil
        shutil.rmtree(proj.dot_path)
        assert not proj.dot_path.exists()

        # Re-resolve with initialize=True should recover
        proj2 = resolve_project(std, config, project_dir=project_dir, initialize=True)
        assert proj2.dot_path.is_dir()

    def test_missing_cfg_file_recovered(self, config_file, tmp_home, credentials_dir):
        config = load_config(config_file)
        std = load_std_paths(config)
        project_dir = str(tmp_home / "project")

        proj = resolve_project(std, config, project_dir=project_dir, initialize=True)
        proj.cfg_file.unlink(missing_ok=True)
        assert not proj.cfg_file.exists()

        proj2 = resolve_project(std, config, project_dir=project_dir, initialize=True)
        assert proj2.cfg_file.exists()

    def test_both_missing_recovered(self, config_file, tmp_home, credentials_dir):
        config = load_config(config_file)
        std = load_std_paths(config)
        project_dir = str(tmp_home / "project")

        proj = resolve_project(std, config, project_dir=project_dir, initialize=True)
        import shutil
        shutil.rmtree(proj.dot_path)
        proj.cfg_file.unlink(missing_ok=True)

        proj2 = resolve_project(std, config, project_dir=project_dir, initialize=True)
        assert proj2.dot_path.is_dir()
        assert proj2.cfg_file.exists()

    def test_no_initialize_skips_recovery(self, config_file, tmp_home, credentials_dir):
        config = load_config(config_file)
        std = load_std_paths(config)
        project_dir = str(tmp_home / "project")

        proj = resolve_project(std, config, project_dir=project_dir, initialize=True)
        import shutil
        shutil.rmtree(proj.dot_path)

        # Without initialize, no recovery
        proj2 = resolve_project(std, config, project_dir=project_dir, initialize=False)
        assert not proj2.dot_path.is_dir()


# ---------------------------------------------------------------------------
# Edge cases: spaces, unicode, symlinks, legacy .rc detection
# ---------------------------------------------------------------------------

class TestPathEdgeCases:
    def test_path_with_spaces(self, tmp_home, config_file, credentials_dir):
        config = load_config(config_file)
        std = load_std_paths(config)
        spaced = tmp_home / "my project"
        spaced.mkdir()
        proj = resolve_project(std, config, project_dir=str(spaced), initialize=True)
        assert proj.project_path == spaced.resolve()
        assert proj.settings_path.is_dir()

    def test_path_with_unicode(self, tmp_home, config_file, credentials_dir):
        config = load_config(config_file)
        std = load_std_paths(config)
        uni = tmp_home / "projeçt_ñ"
        uni.mkdir()
        proj = resolve_project(std, config, project_dir=str(uni), initialize=True)
        assert proj.project_path == uni.resolve()

    def test_symlink_resolved(self, tmp_home, config_file, credentials_dir):
        config = load_config(config_file)
        std = load_std_paths(config)
        real = tmp_home / "real_project"
        real.mkdir()
        link = tmp_home / "link_project"
        link.symlink_to(real)
        proj = resolve_project(std, config, project_dir=str(link), initialize=True)
        assert proj.project_path == real.resolve()

    def test_legacy_rc_detection(self, tmp_home):
        """load_std_paths raises ConfigError mentioning legacy .rc if present."""
        config_dir = tmp_home / "config" / "kanibako"
        config_dir.mkdir(parents=True)
        (config_dir / "kanibako.rc").write_text("CLODBOX_DOT_PATH=x\n")
        with pytest.raises(ConfigError, match="Legacy config"):
            load_std_paths()
