/**
 * API client for the Savas Knowledge Base backend.
 */

const API_BASE = import.meta.env.PROD
  ? '/knowledge-base/api'
  : 'http://localhost:8000/api';

export interface Stats {
  chromadb: {
    total_chunks: number;
    description: string;
  };
  sqlite: {
    description: string;
    teamwork: {
      projects: number;
      tasks: number;
      messages: number;
    };
    harvest: {
      clients: number;
      projects: number;
      time_entries: number;
    };
    fathom: {
      transcripts: number;
    };
    github: {
      files: number;
      issues: number;
    };
    drive: {
      documents: number;
    };
  };
}

export async function getStats(): Promise<Stats> {
  const res = await fetch(`${API_BASE}/stats`);
  if (!res.ok) {
    throw new Error(`Failed to fetch stats: ${res.status}`);
  }
  return res.json();
}

export interface SearchRequest {
  query: string;
  top_k?: number;
  source_types?: string[];
  project?: string;
  client?: string;
}

export interface SearchResult {
  score: number;
  content: string;
  source_type: string;
  channel?: string;
  timestamp?: string;
  author?: string;
  source_url?: string;
}

export interface SearchResponse {
  query: string;
  answer: string;
  sources_used: number;
  results: SearchResult[];
}

export async function search(request: SearchRequest): Promise<SearchResponse> {
  const res = await fetch(`${API_BASE}/search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  if (!res.ok) {
    throw new Error(`Search failed: ${res.status}`);
  }
  return res.json();
}
