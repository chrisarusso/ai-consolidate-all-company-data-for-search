"""
SQLite store for raw data from all sources.

Stores raw data before chunking/embedding, allowing flexibility
to change chunking strategies later.
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime, date
from typing import Optional, Any
from contextlib import contextmanager


class SQLiteStore:
    """
    SQLite storage for raw data from all sources.

    Tables:
    - tw_projects, tw_tasks, tw_messages (Teamwork)
    - h_clients, h_projects, h_time_entries (Harvest)
    - f_transcripts (Fathom)
    - gh_files, gh_issues (GitHub)
    - d_documents (Google Drive)
    """

    SCHEMA = """
    -- Teamwork
    CREATE TABLE IF NOT EXISTS tw_projects (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT,
        company_name TEXT,
        status TEXT,
        created_on DATETIME,
        last_changed_on DATETIME,
        fetched_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS tw_tasks (
        id TEXT PRIMARY KEY,
        project_id TEXT,
        project_name TEXT,
        content TEXT NOT NULL,
        description TEXT,
        status TEXT,
        priority TEXT,
        assignees TEXT,
        created_on DATETIME,
        due_date DATETIME,
        completed_on DATETIME,
        fetched_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS tw_messages (
        id TEXT PRIMARY KEY,
        project_id TEXT,
        project_name TEXT,
        title TEXT,
        body TEXT,
        author TEXT,
        posted_on DATETIME,
        category TEXT,
        fetched_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    -- Harvest
    CREATE TABLE IF NOT EXISTS h_clients (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        is_active BOOLEAN,
        fetched_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS h_projects (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        code TEXT,
        client_id INTEGER,
        client_name TEXT,
        is_active BOOLEAN,
        is_billable BOOLEAN,
        notes TEXT,
        created_at DATETIME,
        updated_at DATETIME,
        fetched_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS h_time_entries (
        id INTEGER PRIMARY KEY,
        spent_date DATE,
        hours REAL,
        notes TEXT,
        project_id INTEGER,
        project_name TEXT,
        client_id INTEGER,
        client_name TEXT,
        task_id INTEGER,
        task_name TEXT,
        user_id INTEGER,
        user_name TEXT,
        is_billable BOOLEAN,
        created_at DATETIME,
        fetched_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    -- Fathom
    CREATE TABLE IF NOT EXISTS f_transcripts (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        date DATETIME,
        duration_seconds INTEGER,
        participants TEXT,
        transcript_text TEXT,
        summary TEXT,
        action_items TEXT,
        recording_url TEXT,
        fetched_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    -- GitHub
    CREATE TABLE IF NOT EXISTS gh_files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        repo TEXT NOT NULL,
        path TEXT NOT NULL,
        content TEXT,
        language TEXT,
        branch TEXT DEFAULT 'main',
        url TEXT,
        fetched_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(repo, path, branch)
    );

    CREATE TABLE IF NOT EXISTS gh_issues (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        repo TEXT NOT NULL,
        number INTEGER NOT NULL,
        title TEXT,
        body TEXT,
        state TEXT,
        is_pr BOOLEAN,
        author TEXT,
        labels TEXT,
        created_at DATETIME,
        updated_at DATETIME,
        url TEXT,
        fetched_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(repo, number)
    );

    -- Google Drive
    CREATE TABLE IF NOT EXISTS d_documents (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        mime_type TEXT,
        content TEXT,
        owners TEXT,
        created_time DATETIME,
        modified_time DATETIME,
        web_view_link TEXT,
        fetched_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize the SQLite store.

        Args:
            db_path: Path to SQLite database. Defaults to data/raw_data.db
        """
        if db_path is None:
            # Default to project's data directory
            project_root = Path(__file__).parent.parent.parent.parent
            db_path = project_root / "data" / "raw_data.db"

        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def _get_connection(self):
        """Get a database connection with context management."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_schema(self):
        """Create all tables if they don't exist."""
        with self._get_connection() as conn:
            conn.executescript(self.SCHEMA)

    def _serialize_datetime(self, dt: Optional[datetime]) -> Optional[str]:
        """Convert datetime to ISO string for storage."""
        if dt is None:
            return None
        return dt.isoformat()

    def _serialize_date(self, d: Optional[date]) -> Optional[str]:
        """Convert date to ISO string for storage."""
        if d is None:
            return None
        return d.isoformat()

    def _serialize_list(self, lst: Optional[list]) -> Optional[str]:
        """Convert list to JSON string for storage."""
        if lst is None:
            return None
        return json.dumps(lst)

    # =========================================================================
    # Teamwork Methods
    # =========================================================================

    def insert_tw_project(self, project: Any) -> None:
        """Insert or replace a Teamwork project."""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO tw_projects
                (id, name, description, company_name, status, created_on, last_changed_on, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                project.id,
                project.name,
                project.description,
                project.company_name,
                project.status,
                self._serialize_datetime(project.created_on),
                self._serialize_datetime(project.last_changed_on),
                datetime.now().isoformat(),
            ))

    def insert_tw_task(self, task: Any) -> None:
        """Insert or replace a Teamwork task."""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO tw_tasks
                (id, project_id, project_name, content, description, status, priority,
                 assignees, created_on, due_date, completed_on, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                task.id,
                task.project_id,
                task.project_name,
                task.content,
                task.description,
                task.status,
                task.priority,
                self._serialize_list(task.assignees),
                self._serialize_datetime(task.created_on),
                self._serialize_datetime(task.due_date),
                self._serialize_datetime(task.completed_on),
                datetime.now().isoformat(),
            ))

    def insert_tw_message(self, message: Any) -> None:
        """Insert or replace a Teamwork message."""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO tw_messages
                (id, project_id, project_name, title, body, author, posted_on, category, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                message.id,
                message.project_id,
                message.project_name,
                message.title,
                message.body,
                message.author,
                self._serialize_datetime(message.posted_on),
                message.category,
                datetime.now().isoformat(),
            ))

    # =========================================================================
    # Harvest Methods
    # =========================================================================

    def insert_h_client(self, client: Any) -> None:
        """Insert or replace a Harvest client."""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO h_clients
                (id, name, is_active, fetched_at)
                VALUES (?, ?, ?, ?)
            """, (
                client.id,
                client.name,
                client.is_active,
                datetime.now().isoformat(),
            ))

    def insert_h_project(self, project: Any) -> None:
        """Insert or replace a Harvest project."""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO h_projects
                (id, name, code, client_id, client_name, is_active, is_billable,
                 notes, created_at, updated_at, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                project.id,
                project.name,
                project.code,
                project.client_id,
                project.client_name,
                project.is_active,
                project.is_billable,
                project.notes,
                self._serialize_datetime(project.created_at),
                self._serialize_datetime(project.updated_at),
                datetime.now().isoformat(),
            ))

    def insert_h_time_entry(self, entry: Any) -> None:
        """Insert or replace a Harvest time entry."""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO h_time_entries
                (id, spent_date, hours, notes, project_id, project_name, client_id, client_name,
                 task_id, task_name, user_id, user_name, is_billable, created_at, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entry.id,
                self._serialize_date(entry.spent_date),
                entry.hours,
                entry.notes,
                entry.project_id,
                entry.project_name,
                entry.client_id,
                entry.client_name,
                entry.task_id,
                entry.task_name,
                entry.user_id,
                entry.user_name,
                entry.is_billable,
                self._serialize_datetime(entry.created_at),
                datetime.now().isoformat(),
            ))

    # =========================================================================
    # Fathom Methods
    # =========================================================================

    def insert_f_transcript(self, transcript: Any) -> None:
        """Insert or replace a Fathom transcript."""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO f_transcripts
                (id, title, date, duration_seconds, participants, transcript_text,
                 summary, action_items, recording_url, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                transcript.id,
                transcript.title,
                self._serialize_datetime(transcript.date),
                transcript.duration_seconds,
                self._serialize_list(transcript.participants),
                transcript.transcript_text,
                transcript.summary,
                self._serialize_list(transcript.action_items),
                transcript.recording_url,
                datetime.now().isoformat(),
            ))

    # =========================================================================
    # GitHub Methods
    # =========================================================================

    def insert_gh_file(self, file: Any) -> None:
        """Insert or replace a GitHub file."""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO gh_files
                (repo, path, content, language, branch, url, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                file.repo,
                file.path,
                file.content,
                file.language,
                file.branch,
                file.url,
                datetime.now().isoformat(),
            ))

    def insert_gh_issue(self, issue: Any) -> None:
        """Insert or replace a GitHub issue/PR."""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO gh_issues
                (repo, number, title, body, state, is_pr, author, labels,
                 created_at, updated_at, url, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                issue.repo,
                issue.number,
                issue.title,
                issue.body,
                issue.state,
                issue.is_pr,
                issue.author,
                self._serialize_list(issue.labels),
                self._serialize_datetime(issue.created_at),
                self._serialize_datetime(issue.updated_at),
                issue.url,
                datetime.now().isoformat(),
            ))

    # =========================================================================
    # Google Drive Methods
    # =========================================================================

    def insert_d_document(self, doc: Any) -> None:
        """Insert or replace a Google Drive document."""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO d_documents
                (id, name, mime_type, content, owners, created_time, modified_time,
                 web_view_link, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                doc.id,
                doc.name,
                doc.mime_type,
                doc.content,
                self._serialize_list(doc.owners),
                self._serialize_datetime(doc.created_time),
                self._serialize_datetime(doc.modified_time),
                doc.web_view_link,
                datetime.now().isoformat(),
            ))

    # =========================================================================
    # Stats Methods
    # =========================================================================

    def get_stats(self) -> dict:
        """Get counts for all tables."""
        with self._get_connection() as conn:
            stats = {}
            tables = [
                ("teamwork_projects", "tw_projects"),
                ("teamwork_tasks", "tw_tasks"),
                ("teamwork_messages", "tw_messages"),
                ("harvest_clients", "h_clients"),
                ("harvest_projects", "h_projects"),
                ("harvest_time_entries", "h_time_entries"),
                ("fathom_transcripts", "f_transcripts"),
                ("github_files", "gh_files"),
                ("github_issues", "gh_issues"),
                ("drive_documents", "d_documents"),
            ]
            for key, table in tables:
                result = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
                stats[key] = result[0]
            return stats

    def clear_all(self) -> None:
        """Delete all data from all tables. Use with caution!"""
        with self._get_connection() as conn:
            tables = [
                "tw_projects", "tw_tasks", "tw_messages",
                "h_clients", "h_projects", "h_time_entries",
                "f_transcripts",
                "gh_files", "gh_issues",
                "d_documents",
            ]
            for table in tables:
                conn.execute(f"DELETE FROM {table}")
