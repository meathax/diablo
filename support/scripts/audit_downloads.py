"""Stream-check every configured game URL without retaining game content."""
import concurrent.futures
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[2]

def check(item):
    path, entry = item
    result = {"path": path, "url": entry["url"]}
    try:
        digest = hashlib.md5()
        size = 0
        with urllib.request.urlopen(entry["url"], timeout=60) as response:
            result["http_status"] = response.status
            for block in iter(lambda: response.read(1024 * 1024), b""):
                digest.update(block)
                size += len(block)
        result.update(bytes=size, md5=digest.hexdigest(),
                      passed=size == entry["size"] and digest.hexdigest() == entry["hash"])
    except Exception as error:
        result.update(passed=False, error=str(error))
    print(json.dumps(result), flush=True)
    return result

if __name__ == "__main__":
    database = json.loads((ROOT / "distribution/diablo_mister.json").read_text())
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(check, database["files"].items()))
    output = ROOT / "reports/downloader-audit.json"
    output.write_text(json.dumps(results, indent=2) + "\n")
    raise SystemExit(0 if all(row["passed"] for row in results) else 1)
