# User Preferences

## Infrastructure
- Prefer Nix and flakes for dev environments and service management. Avoid Docker when possible.
- When Docker is the only upstream option, present the tradeoffs and explore Nix-native alternatives before defaulting to Docker.

## Dotfiles & Skills
- Claude Code skills and global config are managed in `~/personal_projects/dotfiles/`
- `~/.claude/skills` and `~/.claude/CLAUDE.md` are symlinks into that repo
- When creating or modifying skills or this file, commit in the dotfiles repo
