interface SourceCardProps {
  name: string;
  icon: string;
  stats: { label: string; count: number }[];
  color: string;
}

export function SourceCard({ name, icon, stats, color }: SourceCardProps) {
  const total = stats.reduce((sum, s) => sum + s.count, 0);

  return (
    <div className={`bg-white rounded-lg shadow-md p-6 border-l-4 ${color}`}>
      <div className="flex items-center gap-3 mb-4">
        <span className="text-2xl">{icon}</span>
        <h3 className="text-lg font-semibold text-gray-800">{name}</h3>
      </div>

      <div className="space-y-2">
        {stats.map((stat) => (
          <div key={stat.label} className="flex justify-between text-sm">
            <span className="text-gray-600">{stat.label}</span>
            <span className="font-medium text-gray-900">
              {stat.count.toLocaleString()}
            </span>
          </div>
        ))}
      </div>

      {stats.length > 1 && (
        <div className="mt-4 pt-3 border-t border-gray-100">
          <div className="flex justify-between text-sm font-medium">
            <span className="text-gray-700">Total</span>
            <span className="text-gray-900">{total.toLocaleString()}</span>
          </div>
        </div>
      )}
    </div>
  );
}
