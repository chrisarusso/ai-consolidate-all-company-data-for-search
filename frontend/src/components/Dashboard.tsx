import { useEffect, useState } from 'react';
import { getStats } from '../api/client';
import type { Stats } from '../api/client';
import { SourceCard } from './SourceCard';

export function Dashboard() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getStats()
      .then(setStats)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-gray-500">Loading...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="bg-red-50 text-red-700 p-4 rounded-lg">
          Error: {error}
        </div>
      </div>
    );
  }

  if (!stats) {
    return null;
  }

  const sources = [
    {
      name: 'Slack',
      icon: '#',
      color: 'border-purple-500',
      stats: [{ label: 'Chunks (ChromaDB)', count: stats.chromadb.total_chunks }],
    },
    {
      name: 'Teamwork',
      icon: '📋',
      color: 'border-blue-500',
      stats: [
        { label: 'Projects', count: stats.sqlite.teamwork.projects },
        { label: 'Tasks', count: stats.sqlite.teamwork.tasks },
        { label: 'Messages', count: stats.sqlite.teamwork.messages },
      ],
    },
    {
      name: 'Harvest',
      icon: '⏱️',
      color: 'border-orange-500',
      stats: [
        { label: 'Clients', count: stats.sqlite.harvest.clients },
        { label: 'Projects', count: stats.sqlite.harvest.projects },
        { label: 'Time Entries', count: stats.sqlite.harvest.time_entries },
      ],
    },
    {
      name: 'Fathom',
      icon: '🎙️',
      color: 'border-green-500',
      stats: [{ label: 'Transcripts', count: stats.sqlite.fathom.transcripts }],
    },
    {
      name: 'GitHub',
      icon: '🐙',
      color: 'border-gray-700',
      stats: [
        { label: 'Files', count: stats.sqlite.github.files },
        { label: 'Issues/PRs', count: stats.sqlite.github.issues },
      ],
    },
    {
      name: 'Google Drive',
      icon: '📄',
      color: 'border-yellow-500',
      stats: [{ label: 'Documents', count: stats.sqlite.drive.documents }],
    },
  ];

  const totalRawRecords =
    stats.sqlite.teamwork.projects +
    stats.sqlite.teamwork.tasks +
    stats.sqlite.teamwork.messages +
    stats.sqlite.harvest.clients +
    stats.sqlite.harvest.projects +
    stats.sqlite.harvest.time_entries +
    stats.sqlite.fathom.transcripts +
    stats.sqlite.github.files +
    stats.sqlite.github.issues +
    stats.sqlite.drive.documents;

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 py-6 flex justify-between items-start">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">
              Savas Knowledge Base
            </h1>
            <p className="text-gray-500 mt-1">
              Unified search across company data sources
            </p>
          </div>
          <a
            href="/"
            className="text-blue-600 hover:text-blue-800 text-sm flex items-center gap-1"
          >
            ← Back to Internal Tools
          </a>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-8">
        {/* Summary Stats */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
          <div className="bg-gradient-to-r from-indigo-500 to-purple-600 rounded-lg p-6 text-white">
            <div className="text-sm opacity-80">Raw Data Records</div>
            <div className="text-3xl font-bold mt-1">
              {totalRawRecords.toLocaleString()}
            </div>
            <div className="text-sm opacity-80 mt-2">
              Stored in SQLite (pre-embedding)
            </div>
          </div>
          <div className="bg-gradient-to-r from-emerald-500 to-teal-600 rounded-lg p-6 text-white">
            <div className="text-sm opacity-80">Embedded Chunks</div>
            <div className="text-3xl font-bold mt-1">
              {stats.chromadb.total_chunks.toLocaleString()}
            </div>
            <div className="text-sm opacity-80 mt-2">
              Ready for semantic search (ChromaDB)
            </div>
          </div>
        </div>

        {/* Source Cards Grid */}
        <h2 className="text-lg font-semibold text-gray-800 mb-4">
          Data Sources
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {sources.map((source) => (
            <SourceCard
              key={source.name}
              name={source.name}
              icon={source.icon}
              stats={source.stats}
              color={source.color}
            />
          ))}
        </div>

        {/* Status Note */}
        <div className="mt-8 bg-blue-50 border border-blue-200 rounded-lg p-4">
          <div className="flex items-start gap-3">
            <span className="text-blue-500 text-xl">ℹ️</span>
            <div>
              <h3 className="font-medium text-blue-800">Current Status</h3>
              <p className="text-blue-700 text-sm mt-1">
                Raw data has been ingested into SQLite. Slack messages from
                #general are already embedded in ChromaDB. Next step: process
                raw data into searchable chunks.
              </p>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
