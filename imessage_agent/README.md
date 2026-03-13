# Bezalel.AI iMessage Sync Agent

A macOS agent that runs in the background and syncs your iMessage history to the Bezalel server. It reads from the local `chat.db` SQLite database, resolves contact names from your address book, encrypts the data with AES-256-GCM, and uploads it on a 30-minute schedule via launchd.

## Prerequisites

- macOS 12 (Monterey) or later
- Python 3.10+
- A Bezalel master API key and encryption key (obtain from the admin dashboard)

## Quick Start

```bash
cd imessage_agent
chmod +x setup_mac.sh
./setup_mac.sh
```

The setup script will:
1. Create a Python virtual environment at `~/.bezalel_venv`
2. Install dependencies
3. Copy agent files to `~/.bezalel_agent`
4. Create the environment file at `~/.bezalel_env` (you must fill in your keys)
5. Install and load the launchd agent

After the script finishes, edit `~/.bezalel_env` and fill in your keys.

## Granting Full Disk Access

macOS protects `~/Library/Messages/chat.db` behind Full Disk Access. The sync agent **will not work** unless you grant access to the Python interpreter.

1. Open **System Settings** (or System Preferences on older macOS).
2. Go to **Privacy & Security > Full Disk Access**.
3. Click the **+** button (you may need to unlock with your password).
4. Navigate to `~/.bezalel_venv/bin/python3` and add it.
   - If the file picker does not show hidden folders, press **Cmd+Shift+.** to reveal them.
   - Alternatively, open Terminal and run:
     ```bash
     open ~/.bezalel_venv/bin/
     ```
     Then drag `python3` into the Full Disk Access list.
5. If your system Python is a symlink (common with Homebrew), you may also need to add the real binary. Find it with:
   ```bash
   readlink -f ~/.bezalel_venv/bin/python3
   ```

## Environment Variables

The file `~/.bezalel_env` must contain:

| Variable | Description |
|---|---|
| `BEZALEL_MASTER_KEY` | Long-lived API key for authenticating with the server to obtain rotating keys. |
| `BEZALEL_ENCRYPTION_KEY` | 64-character hex string (256-bit AES key) used to encrypt message payloads before upload. |
| `BEZALEL_SERVER_URL` | Server URL. Defaults to `https://www.danieltaehyunpark.com` if not set. |

Generate an encryption key:
```bash
python3 -c "import os; print(os.urandom(32).hex())"
```

## Verifying the Sync

Check that the launchd agent is loaded:
```bash
launchctl list | grep bezalel
```

Watch the log in real time:
```bash
tail -f ~/Library/Logs/bezalel_sync.log
```

Trigger a manual sync:
```bash
~/.bezalel_venv/bin/python3 ~/.bezalel_agent/bezalel_imessage_sync.py
```

Trigger a full sync (last 3 years, ignoring the previous sync checkpoint):
```bash
~/.bezalel_venv/bin/python3 ~/.bezalel_agent/bezalel_imessage_sync.py --full-sync
```

## How It Works

1. **Schedule**: launchd runs the agent every 30 minutes (and once at login).
2. **Read**: The agent opens `~/Library/Messages/chat.db` in read-only mode and queries for messages newer than the last sync checkpoint.
3. **Contacts**: It uses AppleScript and the macOS Contacts framework to map phone numbers and email addresses to display names.
4. **Encrypt**: The message payload is serialized to JSON and encrypted with AES-256-GCM using the pre-shared encryption key.
5. **Upload**: The encrypted payload is sent to the server with a rotating API key in the Authorization header.
6. **Checkpoint**: On success, the timestamp of the newest synced message is saved to `~/.bezalel_sync_state` so the next run only picks up new messages.

## Troubleshooting

### "chat.db not found"
The agent cannot locate `~/Library/Messages/chat.db`. Make sure you have iMessage enabled and have sent or received at least one message.

### "database is locked"
The Messages app is actively writing to the database. The agent will retry automatically on the next scheduled run (30 minutes). This is harmless.

### "Failed to fetch rotating API key"
- Verify `BEZALEL_MASTER_KEY` is set correctly in `~/.bezalel_env`.
- Verify the server URL is correct and reachable:
  ```bash
  curl -I https://www.danieltaehyunpark.com/api/imessage/key
  ```

### "BEZALEL_ENCRYPTION_KEY is not set"
Edit `~/.bezalel_env` and add your 64-character hex encryption key.

### Agent not running after reboot
Verify the plist is loaded:
```bash
launchctl load ~/Library/LaunchAgents/com.bezalel.imessagesync.plist
```

### No messages synced but no errors
- Check that Full Disk Access has been granted (see above).
- Run a manual sync with `--full-sync` and watch the log output.

## Uninstalling

```bash
launchctl unload ~/Library/LaunchAgents/com.bezalel.imessagesync.plist
rm ~/Library/LaunchAgents/com.bezalel.imessagesync.plist
rm -rf ~/.bezalel_venv
rm -rf ~/.bezalel_agent
rm -f ~/.bezalel_env
rm -f ~/.bezalel_sync_state
```
