"""
Teamwork data loader.

Handles loading projects, tasks, and messages from Teamwork
and converting them into chunks for the vector store.
"""

import requests
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional
from pydantic import BaseModel, Field

from ..config import TEAMWORK_DIR, TEAMWORK_API_KEY, TEAMWORK_SITE
from ..models import Chunk, SourceType
from ..storage.chroma_store import generate_chunk_id


class TeamworkProject(BaseModel):
    """A Teamwork project."""
    id: str
    name: str
    description: Optional[str] = None
    company_name: Optional[str] = None
    status: str = "active"
    created_on: Optional[datetime] = None
    last_changed_on: Optional[datetime] = None


class TeamworkTask(BaseModel):
    """A Teamwork task."""
    id: str
    project_id: str
    project_name: str
    content: str
    description: Optional[str] = None
    status: str
    priority: Optional[str] = None
    assignees: list[str] = Field(default_factory=list)
    created_on: Optional[datetime] = None
    due_date: Optional[datetime] = None
    completed_on: Optional[datetime] = None


class TeamworkMessage(BaseModel):
    """A Teamwork message/comment."""
    id: str
    project_id: str
    project_name: str
    title: str
    body: str
    author: str
    posted_on: datetime
    category: Optional[str] = None


class TeamworkLoader:
    """
    Load and process Teamwork data via API.

    Supports:
    - Projects with metadata
    - Tasks with descriptions
    - Messages/comments
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        site: Optional[str] = None,
        data_dir: Optional[Path] = None,
    ):
        """
        Initialize the Teamwork loader.

        Args:
            api_key: Teamwork API key.
            site: Teamwork site (e.g., "company.teamwork.com").
            data_dir: Path to cache directory.
        """
        self.api_key = api_key or TEAMWORK_API_KEY
        self.site = site or TEAMWORK_SITE
        self.data_dir = data_dir or TEAMWORK_DIR
        self.base_url = f"https://{self.site}"

        if not self.api_key:
            raise ValueError("Teamwork API key required. Set TEAMWORK_API_KEY env var.")

    def _request(self, endpoint: str, params: Optional[dict] = None) -> dict:
        """Make an authenticated request to Teamwork API."""
        url = f"{self.base_url}/{endpoint}"
        response = requests.get(
            url,
            auth=(self.api_key, "x"),  # Teamwork uses API key as username
            params=params or {},
        )
        response.raise_for_status()
        return response.json()

    def _parse_datetime(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse Teamwork datetime string."""
        if not date_str:
            return None
        try:
            # Teamwork uses format: "2024-01-15T10:30:00Z"
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return None

    def list_projects(
        self,
        status: str = "ALL",
        limit: int = 500,
    ) -> Iterator[TeamworkProject]:
        """
        List all projects.

        Args:
            status: Filter by status (ALL, ACTIVE, ARCHIVED).
            limit: Maximum projects to return.

        Yields:
            TeamworkProject objects.
        """
        page = 1
        page_size = 100
        count = 0

        while count < limit:
            response = self._request("projects.json", {
                "status": status,
                "page": page,
                "pageSize": min(page_size, limit - count),
            })

            projects = response.get("projects", [])
            if not projects:
                break

            for proj in projects:
                yield TeamworkProject(
                    id=str(proj["id"]),
                    name=proj.get("name", ""),
                    description=proj.get("description"),
                    company_name=proj.get("company", {}).get("name"),
                    status=proj.get("status", "active"),
                    created_on=self._parse_datetime(proj.get("createdOn")),
                    last_changed_on=self._parse_datetime(proj.get("lastChangedOn")),
                )
                count += 1
                if count >= limit:
                    break

            page += 1

    def list_tasks(
        self,
        project_id: Optional[str] = None,
        include_completed: bool = True,
        limit: int = 1000,
    ) -> Iterator[TeamworkTask]:
        """
        List tasks, optionally filtered by project.

        Args:
            project_id: Filter by specific project.
            include_completed: Include completed tasks.
            limit: Maximum tasks to return.

        Yields:
            TeamworkTask objects.
        """
        # Get projects for name lookup
        projects_map = {}
        for proj in self.list_projects():
            projects_map[proj.id] = proj.name

        page = 1
        page_size = 100
        count = 0

        while count < limit:
            params = {
                "page": page,
                "pageSize": min(page_size, limit - count),
                "includeCompletedTasks": str(include_completed).lower(),
            }

            if project_id:
                endpoint = f"projects/{project_id}/tasks.json"
            else:
                endpoint = "tasks.json"

            try:
                response = self._request(endpoint, params)
            except requests.exceptions.HTTPError:
                break

            tasks = response.get("todo-items", response.get("tasks", []))
            if not tasks:
                break

            for task in tasks:
                proj_id = str(task.get("project-id", task.get("projectId", "")))

                # Get assignees
                assignees = []
                if "responsible-party-names" in task:
                    assignees = [task["responsible-party-names"]]
                elif "assignees" in task:
                    assignees = [a.get("name", "") for a in task.get("assignees", [])]

                yield TeamworkTask(
                    id=str(task["id"]),
                    project_id=proj_id,
                    project_name=projects_map.get(proj_id, "Unknown"),
                    content=task.get("content", task.get("name", "")),
                    description=task.get("description"),
                    status=task.get("status", ""),
                    priority=task.get("priority"),
                    assignees=assignees,
                    created_on=self._parse_datetime(task.get("created-on", task.get("createdOn"))),
                    due_date=self._parse_datetime(task.get("due-date", task.get("dueDate"))),
                    completed_on=self._parse_datetime(task.get("completed-on", task.get("completedOn"))),
                )
                count += 1
                if count >= limit:
                    break

            page += 1

    def list_messages(
        self,
        project_id: Optional[str] = None,
        limit: int = 500,
    ) -> Iterator[TeamworkMessage]:
        """
        List messages/posts from projects.

        Args:
            project_id: Filter by specific project.
            limit: Maximum messages to return.

        Yields:
            TeamworkMessage objects.
        """
        # Get projects for name lookup
        projects_map = {}
        for proj in self.list_projects():
            projects_map[proj.id] = proj.name

        page = 1
        page_size = 100
        count = 0

        while count < limit:
            params = {
                "page": page,
                "pageSize": min(page_size, limit - count),
            }

            if project_id:
                endpoint = f"projects/{project_id}/posts.json"
            else:
                endpoint = "posts.json"

            try:
                response = self._request(endpoint, params)
            except requests.exceptions.HTTPError:
                break

            messages = response.get("posts", [])
            if not messages:
                break

            for msg in messages:
                proj_id = str(msg.get("project-id", msg.get("projectId", "")))

                # Get author name
                author = "Unknown"
                if "author-firstname" in msg:
                    author = f"{msg.get('author-firstname', '')} {msg.get('author-lastname', '')}".strip()
                elif "author" in msg:
                    author = msg["author"].get("name", "Unknown")

                yield TeamworkMessage(
                    id=str(msg["id"]),
                    project_id=proj_id,
                    project_name=projects_map.get(proj_id, "Unknown"),
                    title=msg.get("title", ""),
                    body=msg.get("body", ""),
                    author=author,
                    posted_on=self._parse_datetime(msg.get("posted-on", msg.get("postedOn"))) or datetime.now(),
                    category=msg.get("category", {}).get("name") if isinstance(msg.get("category"), dict) else None,
                )
                count += 1
                if count >= limit:
                    break

            page += 1

    def projects_to_chunks(
        self,
        projects: Iterator[TeamworkProject],
    ) -> Iterator[Chunk]:
        """
        Convert Teamwork projects to chunks.

        Args:
            projects: Iterator of TeamworkProject objects.

        Yields:
            Chunk objects ready for storage.
        """
        for project in projects:
            content = f"[Teamwork Project: {project.name}]\n"
            content += f"Status: {project.status}\n"

            if project.company_name:
                content += f"Client: {project.company_name}\n"

            if project.description:
                content += f"\n{project.description}"

            chunk_id = generate_chunk_id("teamwork", f"project:{project.id}", content)

            yield Chunk(
                id=chunk_id,
                content=content,
                source_type=SourceType.TEAMWORK,
                source_id=f"project:{project.id}",
                source_url=f"{self.base_url}/app/projects/{project.id}",
                timestamp=project.last_changed_on or project.created_on or datetime.now(),
                project=project.name,
                client=project.company_name,
            )

    def tasks_to_chunks(
        self,
        tasks: Iterator[TeamworkTask],
        max_chunk_size: int = 2000,
    ) -> Iterator[Chunk]:
        """
        Convert Teamwork tasks to chunks.

        Args:
            tasks: Iterator of TeamworkTask objects.
            max_chunk_size: Maximum characters per chunk.

        Yields:
            Chunk objects ready for storage.
        """
        for task in tasks:
            content = f"[Teamwork Task - {task.project_name}]\n"
            content += f"Task: {task.content}\n"
            content += f"Status: {task.status}\n"

            if task.priority:
                content += f"Priority: {task.priority}\n"

            if task.assignees:
                content += f"Assigned to: {', '.join(task.assignees)}\n"

            if task.due_date:
                content += f"Due: {task.due_date.strftime('%Y-%m-%d')}\n"

            if task.description:
                # Truncate description if needed
                desc = task.description[:max_chunk_size - len(content) - 50]
                content += f"\n{desc}"

            chunk_id = generate_chunk_id("teamwork", f"task:{task.id}", content)

            yield Chunk(
                id=chunk_id,
                content=content,
                source_type=SourceType.TEAMWORK,
                source_id=f"task:{task.id}",
                source_url=f"{self.base_url}/app/tasks/{task.id}",
                timestamp=task.created_on or datetime.now(),
                author=task.assignees[0] if task.assignees else None,
                project=task.project_name,
            )

    def messages_to_chunks(
        self,
        messages: Iterator[TeamworkMessage],
        max_chunk_size: int = 2000,
    ) -> Iterator[Chunk]:
        """
        Convert Teamwork messages to chunks.

        Args:
            messages: Iterator of TeamworkMessage objects.
            max_chunk_size: Maximum characters per chunk.

        Yields:
            Chunk objects ready for storage.
        """
        for msg in messages:
            content = f"[Teamwork Message - {msg.project_name}]\n"
            content += f"Title: {msg.title}\n"
            content += f"Posted by: {msg.author}\n"

            if msg.category:
                content += f"Category: {msg.category}\n"

            content += f"\n{msg.body}"

            # Truncate if needed
            if len(content) > max_chunk_size:
                content = content[:max_chunk_size - 3] + "..."

            chunk_id = generate_chunk_id("teamwork", f"message:{msg.id}", content)

            yield Chunk(
                id=chunk_id,
                content=content,
                source_type=SourceType.TEAMWORK,
                source_id=f"message:{msg.id}",
                source_url=f"{self.base_url}/app/messages/{msg.id}",
                timestamp=msg.posted_on,
                author=msg.author,
                project=msg.project_name,
            )

    def load_and_chunk(
        self,
        include_projects: bool = True,
        include_tasks: bool = True,
        include_messages: bool = True,
        project_limit: int = 500,
        task_limit: int = 5000,
        message_limit: int = 1000,
    ) -> Iterator[Chunk]:
        """
        Load all Teamwork data and convert to chunks.

        Args:
            include_projects: Include project metadata.
            include_tasks: Include tasks.
            include_messages: Include messages/posts.
            project_limit: Max projects.
            task_limit: Max tasks.
            message_limit: Max messages.

        Yields:
            Chunk objects ready for storage.
        """
        if include_projects:
            print("Loading Teamwork projects...")
            projects = list(self.list_projects(limit=project_limit))
            print(f"  Found {len(projects)} projects")
            yield from self.projects_to_chunks(iter(projects))

        if include_tasks:
            print("Loading Teamwork tasks...")
            tasks = list(self.list_tasks(limit=task_limit))
            print(f"  Found {len(tasks)} tasks")
            yield from self.tasks_to_chunks(iter(tasks))

        if include_messages:
            print("Loading Teamwork messages...")
            messages = list(self.list_messages(limit=message_limit))
            print(f"  Found {len(messages)} messages")
            yield from self.messages_to_chunks(iter(messages))
