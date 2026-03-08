'use client';

import { useState } from 'react';
import type { M4StepOutput } from '@/types';

interface Props {
  data: M4StepOutput;
}

const LEVEL_COLORS: Record<string, string> = {
  '松': 'bg-emerald-100 text-emerald-700 border-emerald-200',
  '竹': 'bg-blue-100 text-blue-700 border-blue-200',
  '梅': 'bg-amber-100 text-amber-700 border-amber-200',
};

export function M4Output({ data }: Props) {
  const [openGapId, setOpenGapId] = useState<string | null>(
    data.proposals[0]?.gap_id ?? null
  );
  const [activeLevel, setActiveLevel] = useState<'松' | '竹' | '梅'>('竹');

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-sm">
        <span className="text-muted-foreground">提案数: <strong>{data.proposals.length}件</strong></span>
        <div className="flex gap-1">
          {(['松', '竹', '梅'] as const).map((lvl) => (
            <button
              key={lvl}
              type="button"
              onClick={() => setActiveLevel(lvl)}
              className={`px-2.5 py-1 text-xs rounded border transition-colors ${
                activeLevel === lvl
                  ? LEVEL_COLORS[lvl]
                  : 'border-input hover:bg-muted/50'
              }`}
            >
              {lvl}
            </button>
          ))}
        </div>
      </div>
      <div className="space-y-1.5 max-h-[400px] overflow-y-auto pr-1">
        {data.proposals.map((ps) => {
          const isOpen = openGapId === ps.gap_id;
          const proposal = activeLevel === '松' ? ps.matsu : activeLevel === '竹' ? ps.take : ps.ume;
          return (
            <div key={ps.gap_id} className="rounded border overflow-hidden">
              <button
                type="button"
                className="w-full flex items-center justify-between px-3 py-2 text-xs hover:bg-muted/30 transition-colors text-left"
                onClick={() => setOpenGapId(isOpen ? null : ps.gap_id)}
              >
                <span className="font-medium truncate pr-2">{ps.disclosure_item}</span>
                <div className="flex items-center gap-2 shrink-0">
                  <span className="text-muted-foreground font-mono">{ps.gap_id}</span>
                  <span className="text-muted-foreground">{isOpen ? '▲' : '▼'}</span>
                </div>
              </button>
              {isOpen && (
                <div className="border-t bg-muted/10 px-3 py-2 space-y-1.5">
                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <span className={`inline-block px-1.5 py-0.5 rounded border ${LEVEL_COLORS[activeLevel]}`}>
                      {activeLevel}レベル
                    </span>
                    <span>{proposal.char_count}字</span>
                  </div>
                  <p className="text-xs leading-relaxed whitespace-pre-wrap">{proposal.text}</p>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
