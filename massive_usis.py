#!/usr/bin/env python3
"""
Build GNPS2-ready USI lists (and launch links) for every MassIVE dataset
matching a keyword search, plus deposition-date metadata for each dataset.

Step 1: query the MassIVE QueryDatasets endpoint for matching datasets.
        The response already carries the deposition date (`createdMillis`),
        so no second metadata API is needed.
Step 2: for each accession, use ppx to list that dataset's mzML files.
Step 3: turn each file into a USI (mzspec:<accession>:<basename>) and pack
        the USIs into classical-networking workflow links.

Outputs (written to --outdir):
    datasets.csv          one row per dataset, incl. deposition date + mzML count
    usis.txt              every USI, one per line
    usis_by_dataset.json  {accession: [usi, ...]}
    gnps2_links.txt       one launch URL per dataset (chunked if long)
    file_cache.json       raw ppx listings, reused on reruns

Install deps:
    pip install requests ppx
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from urllib.parse import quote

import requests
import ppx

KEYWORD = "mscollaboratory"
QUERY_URL = "https://massive.ucsd.edu/ProteoSAFe/QueryDatasets"
GNPS2_BASE = "https://gnps2.org/workflowinput?workflowname=classical_networking_workflow"

# Browsers and the GNPS2 form both tolerate long URLs, but keep each link
# comfortably under this so it survives copy/paste through chat and email.
MAX_URL_CHARS = 8000


def fetch_datasets(keyword, page_size=3000):
    """Return one dict per MSV dataset matching the keyword search.

    The QueryDatasets rows carry the deposition date directly, so this is the
    only call needed for the metadata side of the pipeline.
    """
    params = {
        "pageSize": page_size,
        "offset": 0,
        "query": json.dumps({"keywords_input": keyword}),
    }
    resp = requests.get(QUERY_URL, params=params, timeout=60)
    resp.raise_for_status()
    payload = resp.json()
    rows = payload.get("row_data", [])

    total = int(payload.get("total_rows", len(rows)))
    if total > len(rows):
        print(
            f"WARNING: server reports {total} rows but returned {len(rows)}; "
            f"raise --page-size",
            file=sys.stderr,
        )

    seen, datasets = set(), []
    for r in rows:
        acc = r.get("dataset")
        if not acc or acc in seen:
            continue
        seen.add(acc)
        datasets.append(
            {
                "accession": acc,
                "title": r.get("title", ""),
                "deposition_date": _to_date(r.get("createdMillis")),
                "user": r.get("user", ""),
                "privacy": r.get("privacy", ""),
                "file_count": r.get("file_count", ""),
            }
        )
    return datasets


def _to_date(millis):
    """MassIVE's createdMillis -> 'YYYY-MM-DD', or '' when absent."""
    if not millis:
        return ""
    try:
        dt = datetime.fromtimestamp(int(millis) / 1000, tz=timezone.utc)
    except (TypeError, ValueError):
        return ""
    return dt.strftime("%Y-%m-%d")


def list_mzml(accession):
    """Return all *.mzML paths for one MassIVE dataset."""
    proj = ppx.find_project(accession)  # auto-detects MassIVE for MSV... ids
    return proj.remote_files("*.mzML")


def build_usis(accession, paths):
    """Turn ppx file paths into USIs.

    ppx returns repository-relative paths ('ccms_peak/foo/BAR.mzML') but a GNPS2
    USI addresses the file by basename, so the leading directories are dropped.
    Basenames repeat across a dataset's subdirectories often enough to matter, so
    duplicates are collapsed here rather than silently inflating the link.
    """
    seen, usis = set(), []
    for path in paths:
        name = os.path.basename(path)
        usi = f"mzspec:{accession}:{name}"
        if usi not in seen:
            seen.add(usi)
            usis.append(usi)
    return usis


def build_link(usis):
    """Build one GNPS2 classical-networking launch URL for a list of USIs.

    The fragment is a JSON object whose "usi" value is the USIs joined by literal
    newline escapes. json.dumps produces exactly the `{"usi": "a\\nb"}` shape the
    workflow form expects; quote() then encodes the quotes and spaces while
    leaving the structural characters intact.
    """
    payload = json.dumps({"usi": "\n".join(usis)})
    return f"{GNPS2_BASE}#{quote(payload, safe='{}:,\\/')}"


def build_links(usis, max_url_chars=MAX_URL_CHARS):
    """Build launch URLs for a dataset, splitting into chunks if a link is long."""
    if not usis:
        return []
    link = build_link(usis)
    if len(link) <= max_url_chars or len(usis) == 1:
        return [link]
    mid = len(usis) // 2
    return build_links(usis[:mid], max_url_chars) + build_links(usis[mid:], max_url_chars)


def load_cache(path):
    if not os.path.exists(path):
        return {}
    with open(path) as fh:
        return json.load(fh)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--keyword", default=KEYWORD, help=f"MassIVE keyword search (default: {KEYWORD})")
    ap.add_argument("--outdir", default=os.path.dirname(os.path.abspath(__file__)) + "/output")
    ap.add_argument("--page-size", type=int, default=3000)
    ap.add_argument("--max-url-chars", type=int, default=MAX_URL_CHARS)
    ap.add_argument("--refresh", action="store_true", help="ignore the ppx file cache and re-list every dataset")
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    cache_path = os.path.join(args.outdir, "file_cache.json")
    cache = {} if args.refresh else load_cache(cache_path)

    datasets = fetch_datasets(args.keyword, args.page_size)
    print(f"Found {len(datasets)} datasets for '{args.keyword}'\n")

    usis_by_dataset, links_by_dataset = {}, {}
    for ds in datasets:
        acc = ds["accession"]
        if acc in cache and cache[acc] is not None:
            paths = cache[acc]
            source = "cached"
        else:
            try:
                paths = list_mzml(acc)
            except Exception as e:
                print(f"{acc}: ERROR ({e})")
                cache[acc] = None
                ds["mzml_count"] = 0
                continue
            cache[acc] = paths
            source = "listed"

        usis = build_usis(acc, paths)
        ds["mzml_count"] = len(usis)
        if usis:
            usis_by_dataset[acc] = usis
            links_by_dataset[acc] = build_links(usis, args.max_url_chars)
        print(f"{acc}: {len(usis)} mzML files ({source})")

    with open(cache_path, "w") as fh:
        json.dump(cache, fh, indent=2)

    with open(os.path.join(args.outdir, "usis_by_dataset.json"), "w") as fh:
        json.dump(usis_by_dataset, fh, indent=2)

    with open(os.path.join(args.outdir, "usis.txt"), "w") as fh:
        for usis in usis_by_dataset.values():
            fh.write("\n".join(usis) + "\n")

    with open(os.path.join(args.outdir, "gnps2_links.txt"), "w") as fh:
        for acc, links in links_by_dataset.items():
            for i, link in enumerate(links, 1):
                part = f" (part {i}/{len(links)})" if len(links) > 1 else ""
                fh.write(f"# {acc}{part} - {len(usis_by_dataset[acc])} files\n{link}\n\n")

    import csv

    fields = ["accession", "deposition_date", "mzml_count", "title", "user", "privacy", "file_count"]
    with open(os.path.join(args.outdir, "datasets.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for ds in datasets:
            ds.setdefault("mzml_count", 0)
            w.writerow(ds)

    total_usis = sum(len(u) for u in usis_by_dataset.values())
    print(f"\nWrote {len(datasets)} datasets / {total_usis} USIs to {args.outdir}")


if __name__ == "__main__":
    main()
