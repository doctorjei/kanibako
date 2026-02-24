"""Tests for kanibako.agents: AgentConfig, load/write agent TOML."""

from __future__ import annotations

from kanibako.agents import (
    AgentConfig,
    agent_toml_path,
    agents_dir,
    load_agent_config,
    write_agent_config,
)


class TestAgentConfigDefaults:
    def test_defaults(self):
        cfg = AgentConfig()
        assert cfg.name == ""
        assert cfg.shell == "standard"
        assert cfg.default_args == []
        assert cfg.state == {}
        assert cfg.env == {}
        assert cfg.shared_caches == {}

    def test_custom_values(self):
        cfg = AgentConfig(
            name="Claude Code",
            shell="minimal",
            default_args=["--verbose"],
            state={"access": "permissive"},
            env={"FOO": "bar"},
            shared_caches={"plugins": ".claude/plugins"},
        )
        assert cfg.name == "Claude Code"
        assert cfg.shell == "minimal"
        assert cfg.default_args == ["--verbose"]
        assert cfg.state == {"access": "permissive"}
        assert cfg.env == {"FOO": "bar"}
        assert cfg.shared_caches == {"plugins": ".claude/plugins"}


class TestAgentsDir:
    def test_default(self, tmp_path):
        result = agents_dir(tmp_path)
        assert result == tmp_path / "agents"

    def test_custom(self, tmp_path):
        result = agents_dir(tmp_path, "my-agents")
        assert result == tmp_path / "my-agents"

    def test_empty_fallback(self, tmp_path):
        result = agents_dir(tmp_path, "")
        assert result == tmp_path / "agents"


class TestAgentTomlPath:
    def test_path(self, tmp_path):
        result = agent_toml_path(tmp_path, "claude")
        assert result == tmp_path / "agents" / "claude.toml"

    def test_custom_agents_dir(self, tmp_path):
        result = agent_toml_path(tmp_path, "claude", "my-agents")
        assert result == tmp_path / "my-agents" / "claude.toml"

    def test_general_agent(self, tmp_path):
        result = agent_toml_path(tmp_path, "general")
        assert result == tmp_path / "agents" / "general.toml"


class TestLoadAgentConfig:
    def test_nonexistent_file_returns_defaults(self, tmp_path):
        cfg = load_agent_config(tmp_path / "missing.toml")
        assert cfg.name == ""
        assert cfg.shell == "standard"
        assert cfg.default_args == []

    def test_load_all_sections(self, tmp_path):
        toml_path = tmp_path / "test.toml"
        toml_path.write_text(
            '[agent]\n'
            'name = "Claude Code"\n'
            'shell = "minimal"\n'
            'default_args = ["--verbose", "--debug"]\n'
            '\n'
            '[state]\n'
            'model = "opus"\n'
            'access = "permissive"\n'
            '\n'
            '[env]\n'
            'MY_VAR = "hello"\n'
            '\n'
            '[shared]\n'
            'plugins = ".claude/plugins"\n'
        )
        cfg = load_agent_config(toml_path)
        assert cfg.name == "Claude Code"
        assert cfg.shell == "minimal"
        assert cfg.default_args == ["--verbose", "--debug"]
        assert cfg.state == {"model": "opus", "access": "permissive"}
        assert cfg.env == {"MY_VAR": "hello"}
        assert cfg.shared_caches == {"plugins": ".claude/plugins"}

    def test_load_agent_section_only(self, tmp_path):
        toml_path = tmp_path / "test.toml"
        toml_path.write_text(
            '[agent]\n'
            'name = "Shell"\n'
        )
        cfg = load_agent_config(toml_path)
        assert cfg.name == "Shell"
        assert cfg.shell == "standard"
        assert cfg.default_args == []
        assert cfg.state == {}
        assert cfg.env == {}
        assert cfg.shared_caches == {}

    def test_load_missing_agent_section(self, tmp_path):
        toml_path = tmp_path / "test.toml"
        toml_path.write_text(
            '[state]\n'
            'access = "safe"\n'
        )
        cfg = load_agent_config(toml_path)
        assert cfg.name == ""
        assert cfg.state == {"access": "safe"}

    def test_load_empty_file(self, tmp_path):
        toml_path = tmp_path / "test.toml"
        toml_path.write_text("")
        cfg = load_agent_config(toml_path)
        assert cfg.name == ""
        assert cfg.shell == "standard"

    def test_default_args_must_be_list(self, tmp_path):
        toml_path = tmp_path / "test.toml"
        toml_path.write_text(
            '[agent]\n'
            'default_args = "not-a-list"\n'
        )
        cfg = load_agent_config(toml_path)
        assert cfg.default_args == []


class TestWriteAgentConfig:
    def test_write_defaults(self, tmp_path):
        path = tmp_path / "agents" / "test.toml"
        cfg = AgentConfig()
        write_agent_config(path, cfg)

        assert path.exists()
        content = path.read_text()
        assert '[agent]' in content
        assert '[state]' in content
        assert '[env]' in content
        assert '[shared]' in content
        assert '# model = "opus"' in content

    def test_write_with_values(self, tmp_path):
        path = tmp_path / "test.toml"
        cfg = AgentConfig(
            name="Claude Code",
            shell="standard",
            default_args=["--verbose"],
            state={"access": "permissive"},
            env={"FOO": "bar"},
            shared_caches={"plugins": ".claude/plugins"},
        )
        write_agent_config(path, cfg)

        content = path.read_text()
        assert 'name = "Claude Code"' in content
        assert 'shell = "standard"' in content
        assert 'default_args = ["--verbose"]' in content
        assert 'access = "permissive"' in content
        assert 'FOO = "bar"' in content
        assert 'plugins = ".claude/plugins"' in content

    def test_model_commented_when_not_in_state(self, tmp_path):
        path = tmp_path / "test.toml"
        cfg = AgentConfig(state={"access": "permissive"})
        write_agent_config(path, cfg)

        content = path.read_text()
        assert '# model = "opus"' in content
        assert 'access = "permissive"' in content

    def test_model_not_commented_when_in_state(self, tmp_path):
        path = tmp_path / "test.toml"
        cfg = AgentConfig(state={"model": "sonnet"})
        write_agent_config(path, cfg)

        content = path.read_text()
        assert 'model = "sonnet"' in content
        # Should NOT have the comment line
        lines = content.split("\n")
        comment_lines = [line for line in lines if line.strip() == '# model = "opus"']
        assert len(comment_lines) == 0

    def test_creates_parent_dirs(self, tmp_path):
        path = tmp_path / "deep" / "nested" / "agent.toml"
        write_agent_config(path, AgentConfig())
        assert path.exists()


class TestRoundTrip:
    def test_write_then_load(self, tmp_path):
        path = tmp_path / "test.toml"
        original = AgentConfig(
            name="Claude Code",
            shell="minimal",
            default_args=["--verbose", "--debug"],
            state={"model": "opus", "access": "permissive"},
            env={"MY_VAR": "hello"},
            shared_caches={"plugins": ".claude/plugins"},
        )
        write_agent_config(path, original)
        loaded = load_agent_config(path)

        assert loaded.name == original.name
        assert loaded.shell == original.shell
        assert loaded.default_args == original.default_args
        assert loaded.state == original.state
        assert loaded.env == original.env
        assert loaded.shared_caches == original.shared_caches

    def test_round_trip_empty_config(self, tmp_path):
        path = tmp_path / "test.toml"
        original = AgentConfig()
        write_agent_config(path, original)
        loaded = load_agent_config(path)

        assert loaded.name == ""
        assert loaded.shell == "standard"
        assert loaded.default_args == []
        assert loaded.state == {}
        assert loaded.env == {}
        assert loaded.shared_caches == {}

    def test_round_trip_multiple_default_args(self, tmp_path):
        path = tmp_path / "test.toml"
        original = AgentConfig(default_args=["--foo", "--bar", "baz"])
        write_agent_config(path, original)
        loaded = load_agent_config(path)
        assert loaded.default_args == ["--foo", "--bar", "baz"]
