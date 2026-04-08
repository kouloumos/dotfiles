---
name: link-local
description: Link or unlink a local library for testing in a consumer project. Handles build, npm install from path, and cleanup. Default action is "link". Use "unlink" to reverse.
disable-model-invocation: true
allowed-tools: Bash, Read, Glob
argument-hint: [link|unlink] [library-path] [consumer-path]
---

# Link Local Library

Link (or unlink) a local npm library into a consumer project for integration testing.

Arguments: `$ARGUMENTS`

## Defaults

If paths are not provided, infer them from the current working directory:
- If the current directory IS a library with a `dist/` build output, use it as the library and ask the user for the consumer path.
- If the current directory has a dependency on a known local library, use it as the consumer.

Common pair (use as default when no paths given):
- **Library**: `/home/kouloumos/schema-labs/projects/diavgeia-cli`
- **Consumer**: `/home/kouloumos/schema-labs/projects/opencouncil-tasks`

## Parse arguments

- First arg: action — `link` (default if omitted) or `unlink`
- Second arg: library path (optional, uses default above)
- Third arg: consumer path (optional, uses default above)

## Important: Nix compatibility

Do NOT use `npm link` (two-step global link). The Nix store is read-only, so `npm link` fails trying to symlink into `/nix/store/.../lib/node_modules/`.

Instead, use `npm install <path>` directly in the consumer. This creates a `file:` dependency in package.json and a symlink in node_modules — no global state needed.

## Procedure: link

### 1. Read library package.json

Read `<library>/package.json` to get the package `name` (e.g. `diavgeia-cli`).

### 2. Build the library

The library must be built before linking. Run the build inside the library's dev shell:

```
nix develop <library> --command bash -c "cd <library> && npm run build"
```

Verify `dist/` exists after build.

### 3. Install from local path

In the consumer project, install the library from its local path:

```
nix develop <consumer> --command bash -c "cd <consumer> && npm install <library-absolute-path>"
```

This adds `"<package-name>": "file:../relative-path"` to the consumer's package.json and creates a symlink at `<consumer>/node_modules/<package-name>` pointing to the library.

### 4. Verify

Run these checks:
- Confirm the symlink exists: `ls -la <consumer>/node_modules/<package-name>`
- Quick import check:
  ```
  nix develop <consumer> --command node -e "import('<package-name>').then(m => console.log('OK:', Object.keys(m).join(', ')))"
  ```

### 5. Report

Tell the user:
- The link is active
- Changes to the library source require re-running `npm run build` in the library (the symlink points to `dist/`)
- How to unlink when done: `/link-local unlink`
- Remind them NOT to commit the consumer's `package.json` / `package-lock.json` changes (they contain the local `file:` reference)

## Procedure: unlink

### 1. Read library package.json

Read `<library>/package.json` to get the package `name`.

### 2. Remove the local dependency

```
nix develop <consumer> --command bash -c "cd <consumer> && npm uninstall <package-name>"
```

This removes the `file:` entry from package.json and deletes the symlink from node_modules.

### 3. Restore consumer state

Discard the package.json and package-lock.json changes that the link introduced:

```
git -C <consumer> checkout package.json package-lock.json
```

Then reinstall to ensure node_modules matches the lock file:

```
nix develop <consumer> --command bash -c "cd <consumer> && npm install"
```

### 4. Verify

- Confirm the symlink is gone: `ls <consumer>/node_modules/<package-name> 2>&1` should fail
- Confirm package.json is clean: `git -C <consumer> diff package.json` should show no changes

### 5. Report

Tell the user the link has been removed and the consumer is back to its original state.
