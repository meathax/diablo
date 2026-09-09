# Diablo + Hellfire `update_all` data database

`diablo_mister.json` is a Downloader_MiSTer custom database generated from
`game_files.json`, using the same individual-Archive.org-member mechanism as
the VoidSW core. It installs precisely the files required by the core's
Hellfire profile into `/media/fat/games/Diablo`:

- `DIABDAT.MPQ` — the base game, including its game data, music and cinematics
- `hellfire.mpq`, `hfmonk.mpq`, `hfmusic.mpq`, and `hfvoice.mpq` — the Hellfire
  expansion, Monk content, music, voices and cinematics

The database deliberately links to Archive.org members inside `Diablo.iso` and
`Hellfire.iso`. It never queues either full disc image, cover art, metadata,
torrents, screenshots, or any other archive member.

To publish it for `update_all`, serve `diablo_mister.json` from this repository
over HTTPS and add a `downloader.ini` entry whose section ID matches the
database ID:

```ini
[diablo_mister]
db_url = https://<published-host>/diablo_mister.json
```

Once the database is published at that URL, enable the `diablo` tag in
`update_all`; all five hash-verified MPQs will be installed automatically. The
launcher must use `/media/fat/games/Diablo` as its `--data-root`.

Regenerate after an intentional inventory change with:

```text
python3 scripts/generate_update_all.py
python3 scripts/generate_update_all.py --check
```
