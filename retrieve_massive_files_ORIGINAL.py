#!/usr/bin/env python3
"""
List all mzML files for every MassIVE dataset matching a keyword search.

Step 1: query the MassIVE QueryDatasets endpoint to collect dataset accessions.
Step 2: for each accession, use ppx to list that dataset's mzML files
        (ppx resolves the MassIVE FTP path for you).

Install deps:
    pip install requests ppx
"""

import json
import requests
import ppx

KEYWORD = "mscollaboratory"
QUERY_URL = "https://massive.ucsd.edu/ProteoSAFe/QueryDatasets"


def get_accessions(keyword, page_size=3000):
    """Return the list of MSV accessions matching a keyword search."""
    params = {
        "pageSize": page_size,
        "offset": 0,
        "query": json.dumps({"keywords_input": keyword}),
    }
    resp = requests.get(QUERY_URL, params=params, timeout=60)
    resp.raise_for_status()
    rows = resp.json().get("row_data", [])

    # the 'dataset' field holds the MSV accession; dedupe, keep order
    seen, accessions = set(), []
    for r in rows:
        acc = r.get("dataset")
        if acc and acc not in seen:
            seen.add(acc)
            accessions.append(acc)
    return accessions


def list_mzml(accession):
    """Return all *.mzML filenames for one MassIVE dataset."""
    proj = ppx.find_project(accession)   # auto-detects MassIVE for MSV... ids
    return proj.remote_files("*.mzML")


def main():
    accessions = get_accessions(KEYWORD)
    print(f"Found {len(accessions)} datasets for '{KEYWORD}'\n")

    results = {}
    for acc in accessions:
        try:
            files = list_mzml(acc)
        except Exception as e:
            print(f"{acc}: ERROR ({e})")
            results[acc] = None
            continue
        print(f"{acc}: {len(files)} mzML files")
        results[acc] = files

    with open("massive_mzml_files.json", "w") as fh:
        json.dump(results, fh, indent=2)
    print("\nWrote massive_mzml_files.json")


if __name__ == "__main__":
    main()