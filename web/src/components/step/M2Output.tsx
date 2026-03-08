'use client';

import type { M2StepOutput } from '@/types';

interface Props {
  data: M2StepOutput;
}

export function M2Output({ data }: Props) {
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3 text-sm">
        <span className="text-muted-foreground">適用法令: <strong>{data.applied_count}件</strong></span>
        {data.warning_count > 0 && (
          <span className="flex items-center gap-1 text-amber-600 font-medium">
            ⚠️ 未確認URL: {data.warning_count}件
          </span>
        )}
      </div>
      <div className="overflow-x-auto rounded border">
        <table className="w-full text-xs">
          <thead className="bg-muted/50">
            <tr>
              <th className="px-3 py-2 text-left font-medium text-muted-foreground">ID</th>
              <th className="px-3 py-2 text-left font-medium text-muted-foreground">カテゴリ</th>
              <th className="px-3 py-2 text-left font-medium text-muted-foreground">法令タイトル</th>
              <th className="px-3 py-2 text-left font-medium text-muted-foreground">URL確認</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {data.entries.map((entry) => (
              <tr key={entry.id} className={`hover:bg-muted/20 transition-colors ${entry.warning ? 'bg-amber-50/50' : ''}`}>
                <td className="px-3 py-1.5 font-mono text-muted-foreground">{entry.id}</td>
                <td className="px-3 py-1.5">
                  <span className="inline-block bg-muted px-1.5 py-0.5 rounded text-xs">
                    {entry.category}
                  </span>
                </td>
                <td className="px-3 py-1.5 max-w-[280px]">
                  <div className="truncate font-medium" title={entry.title}>{entry.title}</div>
                  {entry.warning && (
                    <div className="text-amber-600 text-xs mt-0.5">⚠️ {entry.warning}</div>
                  )}
                </td>
                <td className="px-3 py-1.5">
                  {entry.source_confirmed === true && (
                    <span className="text-green-600">✅ 確認済</span>
                  )}
                  {entry.source_confirmed === false && (
                    <span className="text-amber-500">⚠️ 未確認</span>
                  )}
                  {entry.source_confirmed === null && (
                    <span className="text-muted-foreground">—</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
