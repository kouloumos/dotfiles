# User Preferences

## Working Principles
- **Promote one-offs to tooling**: if the same ad-hoc script or probe is needed twice (introspection, data extraction, API queries), extend the project's CLI/tooling instead of writing another inline one-off. One-offs die with the session; tool commands are reviewable, reusable, and compound. When writing a one-off, note that a second occurrence means promotion.
- **Confirm before public actions**: commenting on PRs/issues, pushing, sending messages — draft the content and show it first, unless explicitly told to proceed.

## Infrastructure
- Prefer Nix and flakes for dev environments and service management. Avoid Docker when possible.
- When Docker is the only upstream option, present the tradeoffs and explore Nix-native alternatives before defaulting to Docker.

## Dotfiles & Skills
- Claude Code skills and global config are managed in `~/personal_projects/dotfiles/`
- `~/.claude/skills` and `~/.claude/CLAUDE.md` are symlinks into that repo
- When creating or modifying skills or this file, commit in the dotfiles repo
