"""
GitHub data loader.

Handles loading code, issues, and PRs from GitHub repositories
using the gh CLI and converting them into chunks for the vector store.
"""

import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional
from pydantic import BaseModel, Field

from ..config import GITHUB_DIR
from ..models import Chunk, SourceType
from ..storage.chroma_store import generate_chunk_id


class GitHubRepo(BaseModel):
    """A GitHub repository."""
    name: str
    full_name: str
    description: Optional[str] = None
    url: str
    default_branch: str = "main"
    language: Optional[str] = None
    updated_at: Optional[datetime] = None


class GitHubIssue(BaseModel):
    """A GitHub issue or PR."""
    number: int
    title: str
    body: Optional[str] = None
    state: str
    author: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    url: str
    labels: list[str] = Field(default_factory=list)
    is_pr: bool = False
    repo: str


class GitHubFile(BaseModel):
    """A file from a GitHub repository."""
    path: str
    content: str
    repo: str
    branch: str
    url: str
    language: Optional[str] = None


class GitHubLoader:
    """
    Load and process GitHub data using the gh CLI.

    Supports loading:
    - Repository metadata
    - Issues and PRs with comments
    - Source code files
    """

    def __init__(
        self,
        org: str = "savaslabs",
        data_dir: Optional[Path] = None,
    ):
        """
        Initialize the GitHub loader.

        Args:
            org: GitHub organization name.
            data_dir: Path to cache directory. Defaults to config.
        """
        self.org = org
        self.data_dir = data_dir or GITHUB_DIR
        self._verify_gh_auth()

    def _verify_gh_auth(self) -> bool:
        """Verify gh CLI is authenticated."""
        try:
            result = subprocess.run(
                ["gh", "auth", "status"],
                capture_output=True,
                text=True,
            )
            return result.returncode == 0
        except FileNotFoundError:
            raise RuntimeError("gh CLI not found. Install with: brew install gh")

    def _run_gh(self, args: list[str]) -> dict | list:
        """Run a gh CLI command and return JSON output."""
        result = subprocess.run(
            ["gh"] + args + ["--json"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"gh command failed: {result.stderr}")
        return json.loads(result.stdout) if result.stdout.strip() else {}

    def list_repos(self, limit: int = 100) -> list[GitHubRepo]:
        """
        List repositories in the organization.

        Args:
            limit: Maximum number of repos to return.

        Returns:
            List of GitHubRepo objects.
        """
        result = subprocess.run(
            [
                "gh", "repo", "list", self.org,
                "--limit", str(limit),
                "--json", "name,nameWithOwner,description,url,defaultBranchRef,primaryLanguage,updatedAt",
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Failed to list repos: {result.stderr}")

        repos = []
        for r in json.loads(result.stdout):
            repos.append(GitHubRepo(
                name=r["name"],
                full_name=r["nameWithOwner"],
                description=r.get("description"),
                url=r["url"],
                default_branch=r.get("defaultBranchRef", {}).get("name", "main") if r.get("defaultBranchRef") else "main",
                language=r.get("primaryLanguage", {}).get("name") if r.get("primaryLanguage") else None,
                updated_at=datetime.fromisoformat(r["updatedAt"].replace("Z", "+00:00")) if r.get("updatedAt") else None,
            ))
        return repos

    def list_issues(
        self,
        repo: str,
        state: str = "all",
        limit: int = 100,
        include_prs: bool = True,
    ) -> Iterator[GitHubIssue]:
        """
        List issues and optionally PRs for a repository.

        Args:
            repo: Repository name (org/repo format or just repo name).
            state: Issue state filter (open, closed, all).
            limit: Maximum number to return.
            include_prs: Whether to include pull requests.

        Yields:
            GitHubIssue objects.
        """
        if "/" not in repo:
            repo = f"{self.org}/{repo}"

        # Get issues
        result = subprocess.run(
            [
                "gh", "issue", "list",
                "--repo", repo,
                "--state", state,
                "--limit", str(limit),
                "--json", "number,title,body,state,author,createdAt,updatedAt,url,labels",
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 and result.stdout.strip():
            for issue in json.loads(result.stdout):
                yield GitHubIssue(
                    number=issue["number"],
                    title=issue["title"],
                    body=issue.get("body"),
                    state=issue["state"],
                    author=issue.get("author", {}).get("login", "unknown") if issue.get("author") else "unknown",
                    created_at=datetime.fromisoformat(issue["createdAt"].replace("Z", "+00:00")),
                    updated_at=datetime.fromisoformat(issue["updatedAt"].replace("Z", "+00:00")) if issue.get("updatedAt") else None,
                    url=issue["url"],
                    labels=[l["name"] for l in issue.get("labels", [])],
                    is_pr=False,
                    repo=repo,
                )

        # Get PRs if requested
        if include_prs:
            result = subprocess.run(
                [
                    "gh", "pr", "list",
                    "--repo", repo,
                    "--state", state,
                    "--limit", str(limit),
                    "--json", "number,title,body,state,author,createdAt,updatedAt,url,labels",
                ],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0 and result.stdout.strip():
                for pr in json.loads(result.stdout):
                    yield GitHubIssue(
                        number=pr["number"],
                        title=pr["title"],
                        body=pr.get("body"),
                        state=pr["state"],
                        author=pr.get("author", {}).get("login", "unknown") if pr.get("author") else "unknown",
                        created_at=datetime.fromisoformat(pr["createdAt"].replace("Z", "+00:00")),
                        updated_at=datetime.fromisoformat(pr["updatedAt"].replace("Z", "+00:00")) if pr.get("updatedAt") else None,
                        url=pr["url"],
                        labels=[l["name"] for l in pr.get("labels", [])],
                        is_pr=True,
                        repo=repo,
                    )

    def get_file_content(
        self,
        repo: str,
        path: str,
        branch: Optional[str] = None,
    ) -> Optional[GitHubFile]:
        """
        Get content of a file from a repository.

        Args:
            repo: Repository name (org/repo format or just repo name).
            path: Path to file in the repository.
            branch: Branch name (defaults to default branch).

        Returns:
            GitHubFile object or None if not found.
        """
        if "/" not in repo:
            repo = f"{self.org}/{repo}"

        branch = branch or "main"

        result = subprocess.run(
            [
                "gh", "api",
                f"/repos/{repo}/contents/{path}",
                "-q", ".content",
                "--header", "Accept: application/vnd.github.raw",
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            return None

        # Determine language from extension
        ext = Path(path).suffix.lower()
        lang_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".jsx": "javascript",
            ".php": "php",
            ".rb": "ruby",
            ".go": "go",
            ".rs": "rust",
            ".java": "java",
            ".md": "markdown",
            ".yml": "yaml",
            ".yaml": "yaml",
            ".json": "json",
            ".css": "css",
            ".scss": "scss",
            ".html": "html",
            ".twig": "twig",
        }

        return GitHubFile(
            path=path,
            content=result.stdout,
            repo=repo,
            branch=branch,
            url=f"https://github.com/{repo}/blob/{branch}/{path}",
            language=lang_map.get(ext),
        )

    def list_files(
        self,
        repo: str,
        path: str = "",
        branch: Optional[str] = None,
        extensions: Optional[list[str]] = None,
    ) -> Iterator[str]:
        """
        List files in a repository directory.

        Args:
            repo: Repository name.
            path: Directory path (empty for root).
            branch: Branch name.
            extensions: Filter by file extensions (e.g., [".py", ".js"]).

        Yields:
            File paths.
        """
        if "/" not in repo:
            repo = f"{self.org}/{repo}"

        # Use git ls-tree via gh api
        branch = branch or "main"

        result = subprocess.run(
            [
                "gh", "api",
                f"/repos/{repo}/git/trees/{branch}?recursive=1",
                "-q", ".tree[].path",
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            return

        for file_path in result.stdout.strip().split("\n"):
            if not file_path:
                continue

            # Apply path filter
            if path and not file_path.startswith(path):
                continue

            # Apply extension filter
            if extensions:
                ext = Path(file_path).suffix.lower()
                if ext not in extensions:
                    continue

            yield file_path

    def issues_to_chunks(
        self,
        issues: Iterator[GitHubIssue],
        max_chunk_size: int = 2000,
    ) -> Iterator[Chunk]:
        """
        Convert GitHub issues/PRs to chunks for indexing.

        Args:
            issues: Iterator of GitHubIssue objects.
            max_chunk_size: Maximum characters per chunk.

        Yields:
            Chunk objects ready for storage.
        """
        for issue in issues:
            issue_type = "PR" if issue.is_pr else "Issue"
            labels_str = ", ".join(issue.labels) if issue.labels else "none"

            content = f"[{issue.repo} {issue_type} #{issue.number}]\n"
            content += f"Title: {issue.title}\n"
            content += f"State: {issue.state}\n"
            content += f"Labels: {labels_str}\n"
            content += f"Author: {issue.author}\n\n"

            if issue.body:
                body = issue.body[:max_chunk_size - len(content) - 50]
                content += body

            chunk_id = generate_chunk_id(
                "github",
                f"{issue.repo}:{issue_type.lower()}:{issue.number}",
                content,
            )

            yield Chunk(
                id=chunk_id,
                content=content,
                source_type=SourceType.GITHUB,
                source_id=f"{issue.repo}#{issue.number}",
                source_url=issue.url,
                timestamp=issue.created_at,
                author=issue.author,
                project=issue.repo.split("/")[-1],
            )

    def files_to_chunks(
        self,
        files: Iterator[GitHubFile],
        max_chunk_size: int = 2000,
    ) -> Iterator[Chunk]:
        """
        Convert GitHub files to chunks for indexing.

        Splits large files into multiple chunks.

        Args:
            files: Iterator of GitHubFile objects.
            max_chunk_size: Maximum characters per chunk.

        Yields:
            Chunk objects ready for storage.
        """
        for file in files:
            content = file.content
            repo_name = file.repo.split("/")[-1]

            # Split large files into chunks
            if len(content) <= max_chunk_size:
                chunks = [content]
            else:
                # Split by lines, keeping chunks under limit
                lines = content.split("\n")
                chunks = []
                current = ""

                for line in lines:
                    if len(current) + len(line) + 1 > max_chunk_size:
                        if current:
                            chunks.append(current)
                        current = line
                    else:
                        current = current + "\n" + line if current else line

                if current:
                    chunks.append(current)

            # Create chunk for each section
            for i, chunk_content in enumerate(chunks):
                header = f"[{file.repo} - {file.path}]"
                if len(chunks) > 1:
                    header += f" (part {i + 1}/{len(chunks)})"
                header += "\n"

                if file.language:
                    header += f"Language: {file.language}\n\n"

                full_content = header + chunk_content

                chunk_id = generate_chunk_id(
                    "github",
                    f"{file.repo}:{file.path}:{i}",
                    full_content,
                )

                yield Chunk(
                    id=chunk_id,
                    content=full_content,
                    source_type=SourceType.GITHUB,
                    source_id=f"{file.repo}:{file.path}",
                    source_url=file.url,
                    timestamp=datetime.now(),  # Files don't have timestamps easily
                    project=repo_name,
                )

    def load_repo_code(
        self,
        repo: str,
        extensions: Optional[list[str]] = None,
        exclude_paths: Optional[list[str]] = None,
    ) -> Iterator[GitHubFile]:
        """
        Load all code files from a repository.

        Args:
            repo: Repository name.
            extensions: File extensions to include (default: common code files).
            exclude_paths: Path patterns to exclude.

        Yields:
            GitHubFile objects.
        """
        if extensions is None:
            extensions = [".py", ".js", ".ts", ".tsx", ".jsx", ".php", ".rb", ".go", ".md", ".yml", ".yaml"]

        if exclude_paths is None:
            exclude_paths = ["node_modules/", "vendor/", ".git/", "dist/", "build/", "__pycache__/"]

        for file_path in self.list_files(repo, extensions=extensions):
            # Check exclusions
            skip = False
            for exclude in exclude_paths:
                if exclude in file_path:
                    skip = True
                    break
            if skip:
                continue

            file = self.get_file_content(repo, file_path)
            if file and file.content:
                yield file

    def load_and_chunk(
        self,
        repos: Optional[list[str]] = None,
        include_code: bool = True,
        include_issues: bool = True,
        code_extensions: Optional[list[str]] = None,
    ) -> Iterator[Chunk]:
        """
        Load all GitHub data and convert to chunks.

        Args:
            repos: Specific repos to load (default: all org repos).
            include_code: Whether to load source code.
            include_issues: Whether to load issues and PRs.
            code_extensions: File extensions for code.

        Yields:
            Chunk objects ready for storage.
        """
        # Get repos to process
        if repos is None:
            repo_list = self.list_repos()
            repos = [r.full_name for r in repo_list]

        for repo in repos:
            print(f"Processing {repo}...")

            # Load issues and PRs
            if include_issues:
                try:
                    issues = self.list_issues(repo)
                    yield from self.issues_to_chunks(issues)
                except Exception as e:
                    print(f"  Warning: Failed to load issues for {repo}: {e}")

            # Load code files
            if include_code:
                try:
                    files = self.load_repo_code(repo, extensions=code_extensions)
                    yield from self.files_to_chunks(files)
                except Exception as e:
                    print(f"  Warning: Failed to load code for {repo}: {e}")
