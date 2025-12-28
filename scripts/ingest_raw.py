#!/usr/bin/env python3
"""
Ingest raw data from all sources into SQLite.

This script pulls data from Teamwork, Harvest, Fathom, GitHub, and Drive
and stores it in the SQLite database for later processing.

Usage:
    python scripts/ingest_raw.py [--source SOURCE] [--dry-run]

Options:
    --source SOURCE   Only ingest from one source (teamwork, harvest, fathom, github, drive)
    --dry-run         Print what would be ingested without actually doing it
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from savas_kb.storage import SQLiteStore
from savas_kb.ingestion import (
    TeamworkLoader,
    HarvestLoader,
    FathomLoader,
    GitHubLoader,
    DriveLoader,
)


def ingest_teamwork(store: SQLiteStore, dry_run: bool = False) -> dict:
    """Ingest all Teamwork data."""
    print("\n" + "=" * 60)
    print("TEAMWORK INGESTION")
    print("=" * 60)

    loader = TeamworkLoader()
    counts = {"projects": 0, "tasks": 0, "messages": 0}

    # Projects
    print("\nLoading projects...")
    projects = list(loader.list_projects(status="ALL", limit=1000))
    print(f"  Found {len(projects)} projects")
    counts["projects"] = len(projects)

    if not dry_run:
        for p in projects:
            store.insert_tw_project(p)
        print(f"  Inserted {len(projects)} projects")

    # Tasks
    print("\nLoading tasks...")
    tasks = list(loader.list_tasks(include_completed=True, limit=10000))
    print(f"  Found {len(tasks)} tasks")
    counts["tasks"] = len(tasks)

    if not dry_run:
        for t in tasks:
            store.insert_tw_task(t)
        print(f"  Inserted {len(tasks)} tasks")

    # Messages
    print("\nLoading messages...")
    messages = list(loader.list_messages(limit=5000))
    print(f"  Found {len(messages)} messages")
    counts["messages"] = len(messages)

    if not dry_run:
        for m in messages:
            store.insert_tw_message(m)
        print(f"  Inserted {len(messages)} messages")

    return counts


def ingest_harvest(store: SQLiteStore, dry_run: bool = False) -> dict:
    """Ingest all Harvest data."""
    print("\n" + "=" * 60)
    print("HARVEST INGESTION")
    print("=" * 60)

    loader = HarvestLoader()
    counts = {"clients": 0, "projects": 0, "time_entries": 0}

    # Clients
    print("\nLoading clients...")
    clients = list(loader.list_clients(limit=500))
    print(f"  Found {len(clients)} clients")
    counts["clients"] = len(clients)

    if not dry_run:
        for c in clients:
            store.insert_h_client(c)
        print(f"  Inserted {len(clients)} clients")

    # Projects
    print("\nLoading projects...")
    projects = list(loader.list_projects(limit=1000))
    print(f"  Found {len(projects)} projects")
    counts["projects"] = len(projects)

    if not dry_run:
        for p in projects:
            store.insert_h_project(p)
        print(f"  Inserted {len(projects)} projects")

    # Time Entries (this is the big one - 216K+)
    print("\nLoading time entries (this may take a while)...")
    time_entries = []
    batch_count = 0
    for entry in loader.list_time_entries(limit=250000):
        time_entries.append(entry)
        if len(time_entries) % 10000 == 0:
            print(f"  Loaded {len(time_entries)} time entries...")

    print(f"  Found {len(time_entries)} time entries total")
    counts["time_entries"] = len(time_entries)

    if not dry_run:
        print("  Inserting time entries (in batches)...")
        for i, entry in enumerate(time_entries):
            store.insert_h_time_entry(entry)
            if (i + 1) % 10000 == 0:
                print(f"    Inserted {i + 1} time entries...")
        print(f"  Inserted {len(time_entries)} time entries")

    return counts


def ingest_fathom(store: SQLiteStore, dry_run: bool = False, limit: int = 2) -> dict:
    """Ingest Fathom transcripts."""
    print("\n" + "=" * 60)
    print("FATHOM INGESTION")
    print("=" * 60)

    loader = FathomLoader()
    counts = {"transcripts": 0}

    print(f"\nLoading {limit} most recent meetings...")
    meetings = list(loader.list_all_meetings(max_meetings=limit + 3))[:limit]
    print(f"  Found {len(meetings)} meetings to process")

    for i, meeting in enumerate(meetings, 1):
        print(f"\n  [{i}/{len(meetings)}] {meeting.title[:50]}...")
        try:
            transcript = loader.get_full_transcript(meeting)
            if transcript.transcript_text:
                counts["transcripts"] += 1
                if not dry_run:
                    store.insert_f_transcript(transcript)
                    print(f"    Inserted transcript ({len(transcript.transcript_text)} chars)")
                else:
                    print(f"    Would insert transcript ({len(transcript.transcript_text)} chars)")
            else:
                print(f"    Skipped (no transcript text)")
        except Exception as e:
            print(f"    Error: {e}")

    return counts


def ingest_github(store: SQLiteStore, dry_run: bool = False, repo: str = "savaslabs.com-website") -> dict:
    """Ingest GitHub repository data."""
    print("\n" + "=" * 60)
    print("GITHUB INGESTION")
    print("=" * 60)

    loader = GitHubLoader(org="savaslabs")
    counts = {"files": 0, "issues": 0}

    full_repo = f"savaslabs/{repo}"

    # Determine default branch
    import subprocess
    import json
    result = subprocess.run(
        ["gh", "repo", "view", full_repo, "--json", "defaultBranchRef"],
        capture_output=True, text=True
    )
    branch = "main"
    if result.returncode == 0:
        data = json.loads(result.stdout)
        branch = data.get("defaultBranchRef", {}).get("name", "main")
    print(f"\nUsing branch: {branch}")

    # Issues and PRs
    print(f"\nLoading issues and PRs from {full_repo}...")
    try:
        issues = list(loader.list_issues(repo, state="all", limit=500, include_prs=True))
        print(f"  Found {len(issues)} issues/PRs")
        counts["issues"] = len(issues)

        if not dry_run:
            for issue in issues:
                store.insert_gh_issue(issue)
            print(f"  Inserted {len(issues)} issues/PRs")
    except Exception as e:
        print(f"  Error loading issues: {e}")

    # Code files - need to use the correct branch
    print(f"\nLoading code files from {full_repo} (branch: {branch})...")
    try:
        # Get file list with correct branch
        file_paths = list(loader.list_files(repo, branch=branch, extensions=[".php", ".twig", ".yml", ".yaml", ".md", ".js", ".ts", ".css", ".scss"]))
        print(f"  Found {len(file_paths)} file paths")

        files = []
        for path in file_paths:
            # Skip excluded paths
            skip = False
            for exclude in ["node_modules/", "vendor/", ".git/", "dist/", "build/"]:
                if exclude in path:
                    skip = True
                    break
            if skip:
                continue

            file = loader.get_file_content(repo, path, branch=branch)
            if file and file.content:
                files.append(file)
                if len(files) % 50 == 0:
                    print(f"    Loaded {len(files)} files...")

        print(f"  Found {len(files)} code files with content")
        counts["files"] = len(files)

        if not dry_run:
            for f in files:
                store.insert_gh_file(f)
            print(f"  Inserted {len(files)} code files")
    except Exception as e:
        print(f"  Error loading files: {e}")
        import traceback
        traceback.print_exc()

    return counts


def ingest_drive(store: SQLiteStore, dry_run: bool = False, doc_ids: list = None) -> dict:
    """Ingest Google Drive documents."""
    print("\n" + "=" * 60)
    print("GOOGLE DRIVE INGESTION")
    print("=" * 60)

    if doc_ids is None:
        # Default to the two specific docs from the plan
        doc_ids = [
            "1ydTy1-lc3VacKwgTha7pACMmKTDuamJR7u1h5E7Eqv0",  # Doc
            "1S6JD4KANS5WL1ToIvCG2tSJef_BAVJiqBa0E2K-ZKUA",  # Slides
        ]

    loader = DriveLoader()
    counts = {"documents": 0}

    from savas_kb.ingestion.drive_loader import DriveDocument

    for doc_id in doc_ids:
        print(f"\nFetching document {doc_id}...")
        try:
            # Fetch directly by ID using the Drive API
            file_info = loader.drive_service.files().get(
                fileId=doc_id,
                fields="id, name, mimeType, createdTime, modifiedTime, owners, webViewLink"
            ).execute()

            doc = DriveDocument(
                id=file_info["id"],
                name=file_info["name"],
                mime_type=file_info["mimeType"],
                created_time=datetime.fromisoformat(file_info["createdTime"].replace("Z", "+00:00")) if file_info.get("createdTime") else None,
                modified_time=datetime.fromisoformat(file_info["modifiedTime"].replace("Z", "+00:00")) if file_info.get("modifiedTime") else None,
                owners=[o.get("emailAddress", o.get("displayName", "unknown")) for o in file_info.get("owners", [])],
                web_view_link=file_info.get("webViewLink"),
            )

            # Get content
            doc_with_content = loader.get_document_with_content(doc)
            print(f"  Name: {doc_with_content.name}")
            print(f"  Type: {doc_with_content.mime_type}")
            print(f"  Content length: {len(doc_with_content.content)} chars")

            if doc_with_content.content:
                counts["documents"] += 1
                if not dry_run:
                    store.insert_d_document(doc_with_content)
                    print(f"  Inserted document")
                else:
                    print(f"  Would insert document")

        except Exception as e:
            print(f"  Error: {e}")
            import traceback
            traceback.print_exc()

    return counts


def main():
    parser = argparse.ArgumentParser(description="Ingest raw data into SQLite")
    parser.add_argument("--source", choices=["teamwork", "harvest", "fathom", "github", "drive"],
                        help="Only ingest from one source")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be ingested")
    args = parser.parse_args()

    print("=" * 60)
    print(f"RAW DATA INGESTION - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    if args.dry_run:
        print("\n*** DRY RUN MODE - No data will be inserted ***\n")

    store = SQLiteStore()
    all_counts = {}

    sources = [args.source] if args.source else ["teamwork", "harvest", "fathom", "github", "drive"]

    for source in sources:
        try:
            if source == "teamwork":
                all_counts["teamwork"] = ingest_teamwork(store, args.dry_run)
            elif source == "harvest":
                all_counts["harvest"] = ingest_harvest(store, args.dry_run)
            elif source == "fathom":
                all_counts["fathom"] = ingest_fathom(store, args.dry_run, limit=2)
            elif source == "github":
                all_counts["github"] = ingest_github(store, args.dry_run)
            elif source == "drive":
                all_counts["drive"] = ingest_drive(store, args.dry_run)
        except Exception as e:
            print(f"\nError ingesting {source}: {e}")
            import traceback
            traceback.print_exc()

    # Summary
    print("\n" + "=" * 60)
    print("INGESTION SUMMARY")
    print("=" * 60)
    for source, counts in all_counts.items():
        print(f"\n{source.upper()}:")
        for key, value in counts.items():
            print(f"  {key}: {value:,}")

    # Final stats from DB
    if not args.dry_run:
        print("\nDatabase Stats:")
        stats = store.get_stats()
        for key, value in stats.items():
            if value > 0:
                print(f"  {key}: {value:,}")


if __name__ == "__main__":
    main()
