'use client';

import type { M3StepOutput } from '@/types';

interface Props {
  data: M3StepOutput;
}

const CHANGE_TYPE_COLORS: Record<string, string> = {
  '追加必須': 'bg-red-100 text-red-700',
  '修正推奨': 'bg-amber-100 text-amber-700',
  '参考': 'bg-blue-100 text-blue-700',
};

export function M3Output({ data }: Props) {
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-3 text-sm">
        <span className="text-muted-foreground">
          ギャップ総数: <strong className="text-destructive">{data.total_gaps}件</strong>
        </span>
        {Object.entries(data.by_change_type).map(([type, count]) => (
          <span key={type} className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full ${CHANGE_TYPE_COLORS[type] ?? 'bg-muted text-muted-foreground'}`}>
            {type}: {count}
          </span>
        ))}
      </div>
      <div className="overflow-x-auto rounded border">
        <table className="w-full text-xs">
          <thead className="bg-muted/50">
            <tr>
              <th className="px-3 py-2 text-left font-medium text-muted-foreground">ID</th>
              <th className="px-3 py-2 text-left font-medium text-muted-foreground">セクション</th>
              <th className="px-3 py-2 text-left font-medium text-muted-foreground">変更種別</th>
              <th className="px-3 py-2 text-left font-medium text-muted-foreground">状態</th>
              <th className="px-3 py-2 text-left font-medium text-muted-foreground">説明</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {data.gaps.map((gap) => (
              <tr key={gap.gap_id} className="hover:bg-muted/20 transition-colors">
                <td className="px-3 py-1.5 font-mono text-muted-foreground text-xs">{gap.gap_id}</td>
                <td className="px-3 py-1.5 max-w-[160px] truncate" title={gap.section_heading}>
                  {gap.section_heading}
                </td>
                <td className="px-3 py-1.5">
                  <span className={`inline-block px-1.5 py-0.5 rounded text-xs ${CHANGE_TYPE_COLORS[gap.change_type] ?? 'bg-muted text-muted-foreground'}`}>
                    {gap.change_type}
                  </span>
                </td>
                <td className="px-3 py-1.5">
                  {gap.has_gap === true && <span className="text-destructive font-medium">ギャップあり</span>}
                  {gap.has_gap === false && <span className="text-green-600">対応済</span>}
                  {gap.has_gap === null && <span className="text-muted-foreground">判定不可</span>}
                </td>
                <td className="px-3 py-1.5 max-w-[240px] text-muted-foreground truncate" title={gap.gap_description ?? gap.evidence_hint}>
                  {gap.gap_description ?? gap.evidence_hint}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
