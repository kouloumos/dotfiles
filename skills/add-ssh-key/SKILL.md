---
name: add-ssh-key
description: "Add an SSH public key to a remote server's authorized_keys file"
argument-hint: "<public-key> <user@host>"
allowed-tools: ["Bash", "Read"]
---

# Add SSH Key to Remote Server

Add an SSH public key to a remote server so a user can authenticate via SSH.

## Input

Parse `$ARGUMENTS` for:
1. **Public key** — a string starting with `ssh-rsa`, `ssh-ed25519`, `ecdsa-sha2-*`, or `sk-*`
2. **Target server** — in `user@host` format (e.g., `root@134.122.74.255`)

If either is missing, ask the user to provide it.

## Validation

### Validate the public key format
- Must start with a recognized key type (`ssh-rsa`, `ssh-ed25519`, `ecdsa-sha2-nistp256`, `ecdsa-sha2-nistp384`, `ecdsa-sha2-nistp521`, `sk-ssh-ed25519@openssh.com`, `sk-ecdsa-sha2-nistp256@openssh.com`)
- Must be a single line (no embedded newlines)
- Must have at least 2 space-separated parts (type + base64 data), optional comment

If invalid, show what was received and ask the user to double-check.

### Verify SSH access to the target server
```bash
ssh -o ConnectTimeout=5 -o BatchMode=yes <user@host> "echo ok"
```

If this fails, inform the user they don't have access to the server and cannot proceed.

## Check for Duplicates

Before adding, check if the key already exists:
```bash
ssh <user@host> "grep -F '<base64-portion-of-key>' ~/.ssh/authorized_keys 2>/dev/null"
```

Extract the base64 portion (second field) for matching. If the key is already present, tell the user and stop — do not add it again.

## Preview and Confirm

Show the user a summary before making changes:

```
SSH KEY ADDITION

Server:  <user@host>
Key:     <key-type> <first 30 chars of base64>...<last 10 chars> <comment>
Comment: <comment from key>

Proceed? (yes / cancel)
```

## Add the Key

After user confirms, append the key to the existing authorized_keys file:

```bash
ssh <user@host> "echo '<full-public-key>' >> ~/.ssh/authorized_keys"
```

Do NOT create directories or change permissions — assume `~/.ssh/authorized_keys` already exists with correct permissions.

## Verify

After adding, confirm the key is present:
```bash
ssh <user@host> "tail -1 ~/.ssh/authorized_keys"
```

Report success and remind the user to have the key owner test access:
```
Key added successfully. Ask them to test with: ssh <user@host>
```
