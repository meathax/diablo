# Diablo + Hellfire Downloader_MiSTer databases

This directory contains the two custom databases needed by Downloader_MiSTer,
which Update All invokes:

- `diablo_runtime.json.zip` installs the core frontend, both visible RBFs, the
  engine, launcher, assets, ABI metadata, and notices. The 257 runtime files are
  transported in one `diablo_runtime.zip` and described by a selective archive
  summary using `arc_id` and `arc_at`.
- `diablo_mister.json.zip` installs the five required game-data files into
  `/media/fat/games/Diablo`. Its entries are generated from the repository-root
  `external_files.csv`, following the MiSTer DB template used by BiosDB_MiSTer.

The game database downloads individual members from the Archive.org
`Diablo.iso` and `Hellfire.iso` archives. It does not download either complete
disc image or any unrelated archive member.

## Registration

Merge the contents of `downloader_meathax_diablo.ini` into
`/media/fat/downloader.ini`:

```ini
[diablo_runtime]
db_url = https://raw.githubusercontent.com/meathax/diablo/main/distribution/diablo_runtime.json.zip

[diablo_mister]
db_url = https://raw.githubusercontent.com/meathax/diablo/main/distribution/diablo_mister.json.zip
```

The section names deliberately match each database's `db_id`. Both URLs and
every runtime fallback URL must be anonymously accessible; a private GitHub
repository returns HTTP 404 to MiSTer and cannot be used as the publication
host.

Update All's separate integration is responsible for merging this required
MiSTer frontend selection into `/media/fat/MiSTer.ini`:

```ini
[Diablo]
main=Diablo
```

Downloader databases cannot install or modify `MiSTer.ini` or `downloader.ini`;
Downloader_MiSTer explicitly rejects those destination paths.

## Generation and verification

Regenerate the CSV-backed game database, compressed database files, runtime
archive, and runtime archive database with:

```text
python3 scripts/generate_update_all.py
```

Verify all generated JSON, compressed JSON, ZIP member paths, sizes, and MD5
hashes against `external_files.csv` and `ready` with:

```text
python3 scripts/generate_update_all.py --check
python3 -m unittest support.tests.test_update_all_database -v
```

The uncompressed JSON files remain beside their compressed forms for review.
Update All should use the `.json.zip` URLs.
