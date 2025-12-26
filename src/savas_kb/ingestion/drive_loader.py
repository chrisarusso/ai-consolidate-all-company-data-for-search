"""
Google Drive data loader.

Handles loading documents from Google Drive using OAuth
and converting them into chunks for the vector store.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional
from pydantic import BaseModel, Field

from ..config import DRIVE_DIR, GOOGLE_CREDENTIALS_FILE, GOOGLE_TOKEN_FILE
from ..models import Chunk, SourceType
from ..storage.chroma_store import generate_chunk_id


class DriveDocument(BaseModel):
    """A Google Drive document."""
    id: str
    name: str
    mime_type: str
    created_time: Optional[datetime] = None
    modified_time: Optional[datetime] = None
    owners: list[str] = Field(default_factory=list)
    web_view_link: Optional[str] = None
    content: str = ""


class DriveLoader:
    """
    Load and process Google Drive documents.

    Supports:
    - Google Docs (text extraction)
    - Google Slides (text from all slides)
    - Google Sheets (cell content)
    - Plain text files
    - PDF files (text extraction)
    """

    def __init__(
        self,
        credentials_file: Optional[Path] = None,
        token_file: Optional[Path] = None,
        data_dir: Optional[Path] = None,
    ):
        """
        Initialize the Drive loader.

        Args:
            credentials_file: Path to OAuth credentials JSON.
            token_file: Path to OAuth token JSON.
            data_dir: Path to cache directory.
        """
        self.credentials_file = credentials_file or GOOGLE_CREDENTIALS_FILE
        self.token_file = token_file or GOOGLE_TOKEN_FILE
        self.data_dir = data_dir or DRIVE_DIR
        self._service = None
        self._docs_service = None
        self._slides_service = None
        self._sheets_service = None

    def _get_credentials(self):
        """Get OAuth credentials, refreshing if needed."""
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request

        if not self.token_file.exists():
            raise RuntimeError(
                f"Token file not found: {self.token_file}. "
                "Run OAuth flow first to generate token."
            )

        with open(self.token_file) as f:
            token_data = json.load(f)

        creds = Credentials(
            token=token_data.get("token"),
            refresh_token=token_data.get("refresh_token"),
            token_uri=token_data.get("token_uri"),
            client_id=token_data.get("client_id"),
            client_secret=token_data.get("client_secret"),
            scopes=token_data.get("scopes"),
        )

        # Refresh if expired
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            # Save refreshed token
            with open(self.token_file, "w") as f:
                json.dump({
                    "token": creds.token,
                    "refresh_token": creds.refresh_token,
                    "token_uri": creds.token_uri,
                    "client_id": creds.client_id,
                    "client_secret": creds.client_secret,
                    "scopes": creds.scopes,
                }, f)

        return creds

    @property
    def drive_service(self):
        """Get or create the Drive API service."""
        if self._service is None:
            from googleapiclient.discovery import build
            creds = self._get_credentials()
            self._service = build("drive", "v3", credentials=creds)
        return self._service

    @property
    def docs_service(self):
        """Get or create the Docs API service."""
        if self._docs_service is None:
            from googleapiclient.discovery import build
            creds = self._get_credentials()
            self._docs_service = build("docs", "v1", credentials=creds)
        return self._docs_service

    @property
    def slides_service(self):
        """Get or create the Slides API service."""
        if self._slides_service is None:
            from googleapiclient.discovery import build
            creds = self._get_credentials()
            self._slides_service = build("slides", "v1", credentials=creds)
        return self._slides_service

    @property
    def sheets_service(self):
        """Get or create the Sheets API service."""
        if self._sheets_service is None:
            from googleapiclient.discovery import build
            creds = self._get_credentials()
            self._sheets_service = build("sheets", "v4", credentials=creds)
        return self._sheets_service

    def list_files(
        self,
        folder_id: Optional[str] = None,
        mime_types: Optional[list[str]] = None,
        query: Optional[str] = None,
        limit: int = 100,
    ) -> Iterator[DriveDocument]:
        """
        List files in Drive.

        Args:
            folder_id: ID of folder to search in.
            mime_types: Filter by MIME types.
            query: Additional query string.
            limit: Maximum number of files.

        Yields:
            DriveDocument objects (without content).
        """
        # Build query
        q_parts = ["trashed=false"]

        if folder_id:
            q_parts.append(f"'{folder_id}' in parents")

        if mime_types:
            mime_q = " or ".join([f"mimeType='{mt}'" for mt in mime_types])
            q_parts.append(f"({mime_q})")

        if query:
            q_parts.append(query)

        query_string = " and ".join(q_parts)

        page_token = None
        count = 0

        while count < limit:
            results = self.drive_service.files().list(
                q=query_string,
                pageSize=min(100, limit - count),
                pageToken=page_token,
                fields="nextPageToken, files(id, name, mimeType, createdTime, modifiedTime, owners, webViewLink)",
            ).execute()

            for file in results.get("files", []):
                yield DriveDocument(
                    id=file["id"],
                    name=file["name"],
                    mime_type=file["mimeType"],
                    created_time=datetime.fromisoformat(file["createdTime"].replace("Z", "+00:00")) if file.get("createdTime") else None,
                    modified_time=datetime.fromisoformat(file["modifiedTime"].replace("Z", "+00:00")) if file.get("modifiedTime") else None,
                    owners=[o.get("emailAddress", o.get("displayName", "unknown")) for o in file.get("owners", [])],
                    web_view_link=file.get("webViewLink"),
                )
                count += 1
                if count >= limit:
                    break

            page_token = results.get("nextPageToken")
            if not page_token:
                break

    def get_doc_content(self, doc_id: str) -> str:
        """
        Extract text content from a Google Doc.

        Args:
            doc_id: The document ID.

        Returns:
            Plain text content.
        """
        doc = self.docs_service.documents().get(documentId=doc_id).execute()

        text_parts = []
        for element in doc.get("body", {}).get("content", []):
            if "paragraph" in element:
                for elem in element["paragraph"].get("elements", []):
                    if "textRun" in elem:
                        text_parts.append(elem["textRun"].get("content", ""))

        return "".join(text_parts)

    def get_slides_content(self, presentation_id: str) -> str:
        """
        Extract text content from a Google Slides presentation.

        Args:
            presentation_id: The presentation ID.

        Returns:
            Plain text content from all slides.
        """
        presentation = self.slides_service.presentations().get(
            presentationId=presentation_id
        ).execute()

        text_parts = []

        for i, slide in enumerate(presentation.get("slides", []), 1):
            slide_text = []

            for element in slide.get("pageElements", []):
                if "shape" in element and "text" in element["shape"]:
                    for text_element in element["shape"]["text"].get("textElements", []):
                        if "textRun" in text_element:
                            slide_text.append(text_element["textRun"].get("content", ""))

            if slide_text:
                text_parts.append(f"--- Slide {i} ---\n" + "".join(slide_text))

        return "\n\n".join(text_parts)

    def get_sheet_content(self, spreadsheet_id: str) -> str:
        """
        Extract text content from a Google Sheet.

        Args:
            spreadsheet_id: The spreadsheet ID.

        Returns:
            Text representation of sheet data.
        """
        spreadsheet = self.sheets_service.spreadsheets().get(
            spreadsheetId=spreadsheet_id,
            includeGridData=False,
        ).execute()

        text_parts = []

        for sheet in spreadsheet.get("sheets", []):
            sheet_title = sheet.get("properties", {}).get("title", "Sheet")

            # Get sheet data
            range_name = f"'{sheet_title}'"
            try:
                result = self.sheets_service.spreadsheets().values().get(
                    spreadsheetId=spreadsheet_id,
                    range=range_name,
                ).execute()

                values = result.get("values", [])
                if values:
                    sheet_text = f"--- {sheet_title} ---\n"
                    for row in values:
                        sheet_text += "\t".join(str(cell) for cell in row) + "\n"
                    text_parts.append(sheet_text)
            except Exception:
                continue

        return "\n\n".join(text_parts)

    def get_document_with_content(self, doc: DriveDocument) -> DriveDocument:
        """
        Fetch full content for a document.

        Args:
            doc: DriveDocument with metadata.

        Returns:
            DriveDocument with content populated.
        """
        content = ""

        try:
            if doc.mime_type == "application/vnd.google-apps.document":
                content = self.get_doc_content(doc.id)
            elif doc.mime_type == "application/vnd.google-apps.presentation":
                content = self.get_slides_content(doc.id)
            elif doc.mime_type == "application/vnd.google-apps.spreadsheet":
                content = self.get_sheet_content(doc.id)
            elif doc.mime_type in ["text/plain", "text/markdown", "text/csv"]:
                # Download text files directly
                content = self.drive_service.files().get_media(
                    fileId=doc.id
                ).execute().decode("utf-8")
        except Exception as e:
            print(f"Warning: Failed to get content for {doc.name}: {e}")

        return DriveDocument(
            id=doc.id,
            name=doc.name,
            mime_type=doc.mime_type,
            created_time=doc.created_time,
            modified_time=doc.modified_time,
            owners=doc.owners,
            web_view_link=doc.web_view_link,
            content=content,
        )

    def documents_to_chunks(
        self,
        documents: Iterator[DriveDocument],
        max_chunk_size: int = 2000,
    ) -> Iterator[Chunk]:
        """
        Convert Drive documents to chunks for indexing.

        Args:
            documents: Iterator of DriveDocument objects with content.
            max_chunk_size: Maximum characters per chunk.

        Yields:
            Chunk objects ready for storage.
        """
        for doc in documents:
            if not doc.content:
                continue

            # Determine doc type for labeling
            type_label = "Doc"
            if "presentation" in doc.mime_type:
                type_label = "Slides"
            elif "spreadsheet" in doc.mime_type:
                type_label = "Sheet"

            content = doc.content

            # Split large documents
            if len(content) <= max_chunk_size:
                chunks = [(content, 0)]
            else:
                # Split by paragraphs/sections
                parts = content.split("\n\n")
                chunks = []
                current = ""

                for part in parts:
                    if len(current) + len(part) + 2 > max_chunk_size:
                        if current:
                            chunks.append((current, len(chunks)))
                        current = part
                    else:
                        current = current + "\n\n" + part if current else part

                if current:
                    chunks.append((current, len(chunks)))

            # Create chunk objects
            for chunk_content, idx in chunks:
                header = f"[Google {type_label}: {doc.name}]"
                if len(chunks) > 1:
                    header += f" (part {idx + 1}/{len(chunks)})"
                header += "\n"

                if doc.owners:
                    header += f"Owner: {doc.owners[0]}\n"
                header += "\n"

                full_content = header + chunk_content

                chunk_id = generate_chunk_id(
                    "drive",
                    f"{doc.id}:{idx}",
                    full_content,
                )

                yield Chunk(
                    id=chunk_id,
                    content=full_content,
                    source_type=SourceType.DRIVE,
                    source_id=doc.id,
                    source_url=doc.web_view_link,
                    timestamp=doc.modified_time or doc.created_time or datetime.now(),
                    author=doc.owners[0] if doc.owners else None,
                )

    def load_and_chunk(
        self,
        folder_id: Optional[str] = None,
        include_docs: bool = True,
        include_slides: bool = True,
        include_sheets: bool = True,
        limit: int = 100,
    ) -> Iterator[Chunk]:
        """
        Load Drive documents and convert to chunks.

        Args:
            folder_id: Specific folder to load from.
            include_docs: Include Google Docs.
            include_slides: Include Google Slides.
            include_sheets: Include Google Sheets.
            limit: Maximum documents to load.

        Yields:
            Chunk objects ready for storage.
        """
        mime_types = []
        if include_docs:
            mime_types.append("application/vnd.google-apps.document")
        if include_slides:
            mime_types.append("application/vnd.google-apps.presentation")
        if include_sheets:
            mime_types.append("application/vnd.google-apps.spreadsheet")

        # List files
        docs = list(self.list_files(
            folder_id=folder_id,
            mime_types=mime_types,
            limit=limit,
        ))

        print(f"Found {len(docs)} documents to process")

        # Load content and convert to chunks
        for i, doc in enumerate(docs, 1):
            print(f"Processing {i}/{len(docs)}: {doc.name}")
            doc_with_content = self.get_document_with_content(doc)
            yield from self.documents_to_chunks([doc_with_content])
