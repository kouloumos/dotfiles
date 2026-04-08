# dotfiles

Personal dotfiles for [Claude Code](https://claude.ai/code) configuration.

## Structure

```
skills/          # Claude Code custom skills (slash commands)
```

Each skill is a directory containing a markdown file with frontmatter (name, description, arguments) and the full prompt. See any skill directory for the format.

## Setup

Skills are symlinked into Claude Code's config directory so they're available as `/skill-name` in any Claude Code session, across all projects.

### NixOS

Managed via an activation script in `configuration.nix`:

```nix
system.activationScripts.claude-skills = ''
  ln -sfn /path/to/dotfiles/skills /home/<user>/.claude/skills
  chown -h <user>:users /home/<user>/.claude/skills
'';
```

### Manual

```bash
ln -sfn /path/to/dotfiles/skills ~/.claude/skills
```
