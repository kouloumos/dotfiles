# User Preferences

## Working Principles
- **Promote one-offs to tooling**: if the same ad-hoc script or probe is needed twice (introspection, data extraction, API queries), extend the project's CLI/tooling instead of writing another inline one-off. One-offs die with the session; tool commands are reviewable, reusable, and compound. When writing a one-off, note that a second occurrence means promotion.
- **Confirm before public actions**: commenting on PRs/issues, pushing, sending messages — draft the content and show it first, unless explicitly told to proceed.
- **Push explicit refs, never `HEAD`**: `git push <remote> <branch>:<branch>`. `HEAD:main` pushes whatever is checked out, and another session can move the branch under you — re-read `git branch --show-current` right before committing, and check `@{u}..HEAD` before pushing. Git's success line reads the same for one commit or twenty.
- **Fit new work into existing paths**: before writing a new module, service, or command, search for where the capability would already live and account for every piece explicitly — "existing `x.y`" or "new, nothing does this". Aggregate reasoning ("this mostly reuses the services") passes when it shouldn't; the per-item verdict is what catches things. When existing code almost fits, change it rather than fork it — a function doing two jobs gets split, not duplicated — and look one level below the obvious public method, where the narrower seam you need often already exists. Genuinely new capabilities are fine; naming them as such is the point.
- **Plan in verifiable slices**: every spec/plan phase must end with observable behavior someone can trigger and watch — stated as "done when: <run X, see Y>", never "code written". Front-load the riskiest unknown into the first slice.

## Infrastructure
- Prefer Nix and flakes for dev environments and service management. Avoid Docker when possible.
- When Docker is the only upstream option, present the tradeoffs and explore Nix-native alternatives before defaulting to Docker.

## Dotfiles & Skills
- Claude Code skills and global config are managed in `~/personal_projects/dotfiles/`
- `~/.claude/skills` and `~/.claude/CLAUDE.md` are symlinks into that repo
- The NixOS system config is managed in `nixos/`; `/etc/nixos` is a symlink into that repo
- When creating or modifying skills or this file, commit in the dotfiles repo
