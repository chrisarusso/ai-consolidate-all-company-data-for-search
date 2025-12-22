"""
Command-line interface for the Savas Knowledge Base.

Provides commands for ingestion, search, and testing.
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

from .config import SLACK_DIR, FATHOM_DIR
from .ingestion import SlackLoader, FathomLoader
from .search import SearchEngine
from .storage import ChromaStore
from .alerts import AlertDetector, SlackNotifier


def cmd_ingest(args):
    """Ingest data from Slack or Fathom exports."""
    store = ChromaStore()

    if args.source == "slack":
        print(f"Loading Slack data from {args.path or SLACK_DIR}...")
        loader = SlackLoader(export_dir=Path(args.path) if args.path else None)

        chunks = list(loader.load_and_chunk(
            channel_filter=args.channels.split(",") if args.channels else None,
        ))

        print(f"Found {len(chunks)} chunks to index...")
        if chunks:
            store.add_chunks(chunks)
            print(f"Indexed {len(chunks)} chunks.")

    elif args.source == "fathom":
        print(f"Loading Fathom data from {args.path or FATHOM_DIR}...")
        loader = FathomLoader(data_dir=Path(args.path) if args.path else None)

        chunks = list(loader.load_and_chunk())

        print(f"Found {len(chunks)} chunks to index...")
        if chunks:
            store.add_chunks(chunks)
            print(f"Indexed {len(chunks)} chunks.")

    print(f"Total chunks in store: {store.count()}")


def cmd_search(args):
    """Search the knowledge base."""
    engine = SearchEngine()

    print(f"\nSearching for: {args.query}\n")
    print("-" * 60)

    response = engine.search(
        query=args.query,
        top_k=args.top_k,
    )

    # Print answer
    print("\n📝 ANSWER:\n")
    print(response.answer)

    # Print sources
    if args.show_sources and response.results:
        print("\n\n📚 SOURCES:\n")
        for i, result in enumerate(response.results[:args.top_k], 1):
            chunk = result.chunk
            print(f"[{i}] Score: {result.score:.3f}")
            print(f"    Source: {chunk.source_type.value} | {chunk.channel or 'unknown'}")
            print(f"    Date: {chunk.timestamp.strftime('%Y-%m-%d') if chunk.timestamp else 'unknown'}")
            print(f"    Content: {chunk.content[:200]}...")
            print()


def cmd_sales_prep(args):
    """Prepare for a sales call."""
    engine = SearchEngine()

    # Read prospect context from file or stdin
    if args.file:
        with open(args.file) as f:
            context = f.read()
    else:
        print("Enter prospect context (Ctrl+D when done):")
        context = sys.stdin.read()

    print(f"\n🎯 SALES PREP\n")
    print("-" * 60)

    response = engine.search_for_sales_prep(context)

    print(response.answer)


def cmd_one_on_one(args):
    """Prepare for a 1:1 meeting."""
    engine = SearchEngine()

    print(f"\n👥 1:1 PREP FOR: {args.name}\n")
    print("-" * 60)

    response = engine.search_for_1on1_prep(
        team_member_name=args.name,
        days_back=args.days,
    )

    print(response.answer)

    if args.show_sources and response.results:
        print("\n\n📚 SOURCES:\n")
        for result in response.results[:5]:
            chunk = result.chunk
            print(f"- [{chunk.timestamp.strftime('%Y-%m-%d') if chunk.timestamp else '?'}] {chunk.content[:100]}...")


def cmd_detect_alerts(args):
    """Detect alerts in recent content."""
    store = ChromaStore()
    detector = AlertDetector(use_llm=not args.no_llm)
    notifier = SlackNotifier()

    # Get recent chunks
    print("Scanning for alerts...")

    # Search for recent content (this is a simple approach - could be improved)
    results = store.search(
        query="discussion meeting update project",
        top_k=args.limit,
    )

    all_alerts = []
    for result in results:
        alerts = detector.detect_signals(result.chunk)
        all_alerts.extend(alerts)

    if not all_alerts:
        print("No alerts detected.")
        return

    print(f"\n⚠️  DETECTED {len(all_alerts)} ALERTS:\n")

    for alert in all_alerts:
        emoji = "🔴" if "RISK" in alert.signal_type.value else "🟢"
        print(f"{emoji} {alert.title}")
        print(f"   Type: {alert.signal_type.value}")
        print(f"   Summary: {alert.summary}")
        print()

    if args.post:
        print("Posting alerts to Slack...")
        notifier.post_alerts(all_alerts)
        print("Done!")


def cmd_stats(args):
    """Show statistics about the knowledge base."""
    store = ChromaStore()

    print("\n📊 KNOWLEDGE BASE STATS\n")
    print("-" * 40)
    print(f"Total chunks: {store.count()}")


def cmd_clear(args):
    """Clear the knowledge base."""
    if not args.yes:
        confirm = input("Are you sure you want to clear all data? (yes/no): ")
        if confirm.lower() != "yes":
            print("Cancelled.")
            return

    store = ChromaStore()
    store.clear()
    print("Knowledge base cleared.")


def main():
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        description="Savas Knowledge Base CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Ingest command
    ingest_parser = subparsers.add_parser("ingest", help="Ingest data from sources")
    ingest_parser.add_argument("source", choices=["slack", "fathom"], help="Data source")
    ingest_parser.add_argument("--path", help="Path to data directory")
    ingest_parser.add_argument("--channels", help="Comma-separated channel names (Slack only)")
    ingest_parser.set_defaults(func=cmd_ingest)

    # Search command
    search_parser = subparsers.add_parser("search", help="Search the knowledge base")
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument("--top-k", type=int, default=5, help="Number of results")
    search_parser.add_argument("--show-sources", action="store_true", help="Show source chunks")
    search_parser.set_defaults(func=cmd_search)

    # Sales prep command
    sales_parser = subparsers.add_parser("sales-prep", help="Prepare for a sales call")
    sales_parser.add_argument("--file", help="File with prospect context")
    sales_parser.set_defaults(func=cmd_sales_prep)

    # 1:1 prep command
    one_on_one_parser = subparsers.add_parser("1on1", help="Prepare for a 1:1")
    one_on_one_parser.add_argument("name", help="Team member name")
    one_on_one_parser.add_argument("--days", type=int, default=30, help="Days to look back")
    one_on_one_parser.add_argument("--show-sources", action="store_true", help="Show sources")
    one_on_one_parser.set_defaults(func=cmd_one_on_one)

    # Alerts command
    alerts_parser = subparsers.add_parser("alerts", help="Detect and post alerts")
    alerts_parser.add_argument("--post", action="store_true", help="Post to Slack")
    alerts_parser.add_argument("--limit", type=int, default=50, help="Chunks to scan")
    alerts_parser.add_argument("--no-llm", action="store_true", help="Keywords only")
    alerts_parser.set_defaults(func=cmd_detect_alerts)

    # Stats command
    stats_parser = subparsers.add_parser("stats", help="Show knowledge base stats")
    stats_parser.set_defaults(func=cmd_stats)

    # Clear command
    clear_parser = subparsers.add_parser("clear", help="Clear the knowledge base")
    clear_parser.add_argument("--yes", action="store_true", help="Skip confirmation")
    clear_parser.set_defaults(func=cmd_clear)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    args.func(args)


if __name__ == "__main__":
    main()
