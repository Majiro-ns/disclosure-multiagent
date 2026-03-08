'use client';

import type { M1StepOutput } from '@/types';

interface Props {
  data: M1StepOutput;
}

export function M1Output({ data }: Props) {
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between text-sm">
        <span className="font-medium">
          {data.company_name || '（企業名未取得）'}
        </span>
        <span className="text-muted-foreground">{data.section_count}セクション検出</span>
      </div>
      <div className="overflow-x-auto rounded border">
        <table className="w-full text-xs">
          <thead className="bg-muted/50">
            <tr>
              <th className="px-3 py-2 text-left font-medium text-muted-foreground">#</th>
              <th className="px-3 py-2 text-left font-medium text-muted-foreground">セクション見出し</th>
              <th className="px-3 py-2 text-left font-medium text-muted-foreground">文字数</th>
              <th className="px-3 py-2 text-left font-medium text-muted-foreground">抜粋</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {data.sections.map((sec, i) => (
              <tr key={i} className="hover:bg-muted/20 transition-colors">
                <td className="px-3 py-1.5 text-muted-foreground">{i + 1}</td>
                <td className="px-3 py-1.5 font-medium max-w-[180px] truncate" title={sec.heading}>
                  {sec.heading}
                </td>
                <td className="px-3 py-1.5 text-right tabular-nums text-muted-foreground">
                  {sec.char_count.toLocaleString()}
                </td>
                <td className="px-3 py-1.5 text-muted-foreground max-w-[260px] truncate" title={sec.text_excerpt}>
                  {sec.text_excerpt}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
