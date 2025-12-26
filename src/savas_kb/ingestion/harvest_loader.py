"""
Harvest data loader.

Handles loading time entries and project data from Harvest
and converting them into chunks for the vector store.
"""

import requests
from datetime import datetime, date
from pathlib import Path
from typing import Iterator, Optional
from pydantic import BaseModel, Field

from ..config import HARVEST_DIR, HARVEST_ACCESS_TOKEN, HARVEST_ACCOUNT_ID
from ..models import Chunk, SourceType
from ..storage.chroma_store import generate_chunk_id


class HarvestClient(BaseModel):
    """A Harvest client."""
    id: int
    name: str
    is_active: bool = True


class HarvestProject(BaseModel):
    """A Harvest project."""
    id: int
    name: str
    code: Optional[str] = None
    client_id: Optional[int] = None
    client_name: Optional[str] = None
    is_active: bool = True
    is_billable: bool = True
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class HarvestTimeEntry(BaseModel):
    """A Harvest time entry."""
    id: int
    spent_date: date
    hours: float
    notes: Optional[str] = None
    project_id: int
    project_name: str
    client_id: Optional[int] = None
    client_name: Optional[str] = None
    task_id: int
    task_name: str
    user_id: int
    user_name: str
    is_billable: bool = True
    created_at: Optional[datetime] = None


class HarvestLoader:
    """
    Load and process Harvest time tracking data.

    Supports:
    - Projects with client info
    - Time entries with notes
    """

    def __init__(
        self,
        access_token: Optional[str] = None,
        account_id: Optional[str] = None,
        data_dir: Optional[Path] = None,
    ):
        """
        Initialize the Harvest loader.

        Args:
            access_token: Harvest API access token.
            account_id: Harvest account ID.
            data_dir: Path to cache directory.
        """
        self.access_token = access_token or HARVEST_ACCESS_TOKEN
        self.account_id = account_id or HARVEST_ACCOUNT_ID
        self.data_dir = data_dir or HARVEST_DIR
        self.base_url = "https://api.harvestapp.com/v2"

        if not self.access_token:
            raise ValueError("Harvest access token required. Set HARVEST_ACCESS_TOKEN env var.")
        if not self.account_id:
            raise ValueError("Harvest account ID required. Set HARVEST_ACCOUNT_ID env var.")

    def _request(self, endpoint: str, params: Optional[dict] = None) -> dict:
        """Make an authenticated request to Harvest API."""
        url = f"{self.base_url}/{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Harvest-Account-Id": str(self.account_id),
            "User-Agent": "Savas Knowledge Base",
        }
        response = requests.get(url, headers=headers, params=params or {})
        response.raise_for_status()
        return response.json()

    def _parse_datetime(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse Harvest datetime string."""
        if not date_str:
            return None
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return None

    def _parse_date(self, date_str: Optional[str]) -> Optional[date]:
        """Parse Harvest date string."""
        if not date_str:
            return None
        try:
            return date.fromisoformat(date_str)
        except (ValueError, AttributeError):
            return None

    def list_clients(self, limit: int = 500) -> Iterator[HarvestClient]:
        """
        List all clients.

        Args:
            limit: Maximum clients to return.

        Yields:
            HarvestClient objects.
        """
        page = 1
        per_page = 100
        count = 0

        while count < limit:
            response = self._request("clients", {
                "page": page,
                "per_page": min(per_page, limit - count),
            })

            clients = response.get("clients", [])
            if not clients:
                break

            for client in clients:
                yield HarvestClient(
                    id=client["id"],
                    name=client["name"],
                    is_active=client.get("is_active", True),
                )
                count += 1
                if count >= limit:
                    break

            if not response.get("next_page"):
                break
            page += 1

    def list_projects(self, limit: int = 1000) -> Iterator[HarvestProject]:
        """
        List all projects.

        Args:
            limit: Maximum projects to return.

        Yields:
            HarvestProject objects.
        """
        page = 1
        per_page = 100
        count = 0

        while count < limit:
            response = self._request("projects", {
                "page": page,
                "per_page": min(per_page, limit - count),
            })

            projects = response.get("projects", [])
            if not projects:
                break

            for proj in projects:
                client = proj.get("client", {})

                yield HarvestProject(
                    id=proj["id"],
                    name=proj["name"],
                    code=proj.get("code"),
                    client_id=client.get("id") if client else None,
                    client_name=client.get("name") if client else None,
                    is_active=proj.get("is_active", True),
                    is_billable=proj.get("is_billable", True),
                    notes=proj.get("notes"),
                    created_at=self._parse_datetime(proj.get("created_at")),
                    updated_at=self._parse_datetime(proj.get("updated_at")),
                )
                count += 1
                if count >= limit:
                    break

            if not response.get("next_page"):
                break
            page += 1

    def list_time_entries(
        self,
        project_id: Optional[int] = None,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
        limit: int = 10000,
    ) -> Iterator[HarvestTimeEntry]:
        """
        List time entries.

        Args:
            project_id: Filter by project.
            from_date: Filter from this date.
            to_date: Filter to this date.
            limit: Maximum entries to return.

        Yields:
            HarvestTimeEntry objects.
        """
        page = 1
        per_page = 100
        count = 0

        while count < limit:
            params = {
                "page": page,
                "per_page": min(per_page, limit - count),
            }

            if project_id:
                params["project_id"] = project_id
            if from_date:
                params["from"] = from_date.isoformat()
            if to_date:
                params["to"] = to_date.isoformat()

            response = self._request("time_entries", params)

            entries = response.get("time_entries", [])
            if not entries:
                break

            for entry in entries:
                project = entry.get("project", {})
                client = entry.get("client", {})
                task = entry.get("task", {})
                user = entry.get("user", {})

                spent_date = self._parse_date(entry.get("spent_date"))
                if not spent_date:
                    continue

                yield HarvestTimeEntry(
                    id=entry["id"],
                    spent_date=spent_date,
                    hours=entry.get("hours", 0),
                    notes=entry.get("notes"),
                    project_id=project.get("id", 0),
                    project_name=project.get("name", "Unknown"),
                    client_id=client.get("id") if client else None,
                    client_name=client.get("name") if client else None,
                    task_id=task.get("id", 0),
                    task_name=task.get("name", "Unknown"),
                    user_id=user.get("id", 0),
                    user_name=user.get("name", "Unknown"),
                    is_billable=entry.get("billable", True),
                    created_at=self._parse_datetime(entry.get("created_at")),
                )
                count += 1
                if count >= limit:
                    break

            if not response.get("next_page"):
                break
            page += 1

    def projects_to_chunks(
        self,
        projects: Iterator[HarvestProject],
    ) -> Iterator[Chunk]:
        """
        Convert Harvest projects to chunks.

        Args:
            projects: Iterator of HarvestProject objects.

        Yields:
            Chunk objects ready for storage.
        """
        for project in projects:
            content = f"[Harvest Project: {project.name}]\n"

            if project.code:
                content += f"Code: {project.code}\n"

            if project.client_name:
                content += f"Client: {project.client_name}\n"

            content += f"Status: {'Active' if project.is_active else 'Inactive'}\n"
            content += f"Billable: {'Yes' if project.is_billable else 'No'}\n"

            if project.notes:
                content += f"\n{project.notes}"

            chunk_id = generate_chunk_id("harvest", f"project:{project.id}", content)

            yield Chunk(
                id=chunk_id,
                content=content,
                source_type=SourceType.HARVEST,
                source_id=f"project:{project.id}",
                timestamp=project.updated_at or project.created_at or datetime.now(),
                project=project.name,
                client=project.client_name,
            )

    def time_entries_to_chunks(
        self,
        entries: Iterator[HarvestTimeEntry],
        group_by: str = "project_day",
        max_chunk_size: int = 2000,
    ) -> Iterator[Chunk]:
        """
        Convert Harvest time entries to chunks.

        Groups entries to create more meaningful chunks.

        Args:
            entries: Iterator of HarvestTimeEntry objects.
            group_by: Grouping strategy - "project_day" or "individual".
            max_chunk_size: Maximum characters per chunk.

        Yields:
            Chunk objects ready for storage.
        """
        if group_by == "individual":
            for entry in entries:
                if not entry.notes:
                    continue  # Skip entries without notes

                content = f"[Harvest Time Entry - {entry.project_name}]\n"
                content += f"Date: {entry.spent_date.isoformat()}\n"
                content += f"Hours: {entry.hours}\n"
                content += f"Task: {entry.task_name}\n"
                content += f"User: {entry.user_name}\n"

                if entry.client_name:
                    content += f"Client: {entry.client_name}\n"

                content += f"\n{entry.notes}"

                chunk_id = generate_chunk_id("harvest", f"time:{entry.id}", content)

                yield Chunk(
                    id=chunk_id,
                    content=content,
                    source_type=SourceType.HARVEST,
                    source_id=f"time:{entry.id}",
                    timestamp=datetime.combine(entry.spent_date, datetime.min.time()),
                    author=entry.user_name,
                    project=entry.project_name,
                    client=entry.client_name,
                )
        else:
            # Group by project and day
            grouped: dict[str, list[HarvestTimeEntry]] = {}

            for entry in entries:
                key = f"{entry.project_id}:{entry.spent_date.isoformat()}"
                if key not in grouped:
                    grouped[key] = []
                grouped[key].append(entry)

            for key, group_entries in grouped.items():
                first = group_entries[0]

                content = f"[Harvest Time - {first.project_name} - {first.spent_date.isoformat()}]\n"

                if first.client_name:
                    content += f"Client: {first.client_name}\n\n"

                total_hours = 0
                users = set()

                for entry in group_entries:
                    total_hours += entry.hours
                    users.add(entry.user_name)

                    if entry.notes:
                        note_line = f"- {entry.user_name} ({entry.hours}h, {entry.task_name}): {entry.notes}\n"
                        if len(content) + len(note_line) < max_chunk_size:
                            content += note_line

                content += f"\nTotal: {total_hours}h by {', '.join(users)}"

                chunk_id = generate_chunk_id("harvest", f"time_group:{key}", content)

                yield Chunk(
                    id=chunk_id,
                    content=content,
                    source_type=SourceType.HARVEST,
                    source_id=f"time_group:{key}",
                    timestamp=datetime.combine(first.spent_date, datetime.min.time()),
                    participants=list(users),
                    project=first.project_name,
                    client=first.client_name,
                )

    def load_and_chunk(
        self,
        include_projects: bool = True,
        include_time_entries: bool = True,
        time_entry_from: Optional[date] = None,
        time_entry_to: Optional[date] = None,
        project_limit: int = 1000,
        time_entry_limit: int = 50000,
        group_time_entries: str = "project_day",
    ) -> Iterator[Chunk]:
        """
        Load all Harvest data and convert to chunks.

        Args:
            include_projects: Include project metadata.
            include_time_entries: Include time entries with notes.
            time_entry_from: Start date for time entries.
            time_entry_to: End date for time entries.
            project_limit: Max projects.
            time_entry_limit: Max time entries.
            group_time_entries: How to group entries ("project_day" or "individual").

        Yields:
            Chunk objects ready for storage.
        """
        if include_projects:
            print("Loading Harvest projects...")
            projects = list(self.list_projects(limit=project_limit))
            print(f"  Found {len(projects)} projects")
            yield from self.projects_to_chunks(iter(projects))

        if include_time_entries:
            print("Loading Harvest time entries...")
            entries = list(self.list_time_entries(
                from_date=time_entry_from,
                to_date=time_entry_to,
                limit=time_entry_limit,
            ))
            print(f"  Found {len(entries)} time entries")

            # Filter to only entries with notes (more meaningful)
            entries_with_notes = [e for e in entries if e.notes]
            print(f"  {len(entries_with_notes)} have notes")

            yield from self.time_entries_to_chunks(
                iter(entries_with_notes),
                group_by=group_time_entries,
            )
