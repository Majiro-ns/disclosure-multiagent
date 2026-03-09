'use client';

import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { TrendingUp, ArrowUpCircle } from 'lucide-react';

// ─── Types ────────────────────────────────────────────────────────────────────

interface TierData {
  tier_score: number;
  tier_label: string;
  upgrade_items: string[];
}

// ─── Mock fallback (C06 API 未完了時) ─────────────────────────────────────────

const MOCK_DATA: TierData = {
  tier_score: 62,
  tier_label: '梅',
  upgrade_items: ['有価証券報告書への人的資本KPI追記', 'SSBJ早期適用宣言'],
};

// ─── Tier config ──────────────────────────────────────────────────────────────

const TIER_CONFIG = {
  梅: {
    textColor: 'text-rose-700',
    badgeClass: 'bg-rose-100 text-rose-700 border-rose-200',
    fillClass: 'bg-rose-400',
    bgClass: 'bg-rose-50',
    dotClass: 'bg-rose-400',
    next: '竹' as const,
    nextThreshold: 60,
    range: [0, 59] as [number, number],
    zoneWidth: '59%',
  },
  竹: {
    textColor: 'text-emerald-700',
    badgeClass: 'bg-emerald-100 text-emerald-700 border-emerald-200',
    fillClass: 'bg-emerald-500',
    bgClass: 'bg-emerald-50',
    dotClass: 'bg-emerald-500',
    next: '松' as const,
    nextThreshold: 80,
    range: [60, 79] as [number, number],
    zoneWidth: '20%',
  },
  松: {
    textColor: 'text-amber-700',
    badgeClass: 'bg-amber-100 text-amber-700 border-amber-200',
    fillClass: 'bg-amber-500',
    bgClass: 'bg-amber-50',
    dotClass: 'bg-amber-500',
    next: null,
    nextThreshold: null,
    range: [80, 100] as [number, number],
    zoneWidth: '21%',
  },
} as const;

type TierLabel = keyof typeof TIER_CONFIG;

// ─── Component ────────────────────────────────────────────────────────────────

interface Props {
  taskId?: string;
}

export function TierProgressGauge({ taskId }: Props) {
  const [data, setData] = useState<TierData>(MOCK_DATA);
  const [isMock, setIsMock] = useState(true);

  useEffect(() => {
    if (!taskId) return;
    // A7 担当: C06 API (/api/scoring/tier) 完了後に実データへ切り替わる
    async function fetchTier() {
      try {
        const resp = await fetch(`/api/scoring/tier?task_id=${encodeURIComponent(taskId!)}`);
        if (!resp.ok) throw new Error('C06 not ready');
        const json: TierData = await resp.json();
        setData(json);
        setIsMock(false);
      } catch {
        // C06 未完了 → モックデータで先行表示
        setData(MOCK_DATA);
        setIsMock(true);
      }
    }
    fetchTier();
  }, [taskId]);

  const label = (data.tier_label in TIER_CONFIG ? data.tier_label : '梅') as TierLabel;
  const conf = TIER_CONFIG[label];
  const score = Math.min(100, Math.max(0, data.tier_score));

  // Points remaining to next tier
  const toNext = conf.nextThreshold !== null ? conf.nextThreshold - score : null;

  // Fill width per zone (each zone's fill is proportional within its range)
  const umeRange = 59;  // 0-59
  const takeRange = 20; // 60-79
  const matsuRange = 21; // 80-100 (21 points)

  const umeFill = score <= 59
    ? `${(score / umeRange) * 100}%`
    : '100%';
  const takeFill = score < 60
    ? '0%'
    : score <= 79
    ? `${((score - 60) / takeRange) * 100}%`
    : '100%';
  const matsuFill = score < 80
    ? '0%'
    : `${((score - 80) / matsuRange) * 100}%`;

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center justify-between text-base">
          <div className="flex items-center gap-2">
            <TrendingUp className="size-4 text-muted-foreground" />
            <span>開示品質スコア</span>
          </div>
          <Badge variant="outline" className={`${conf.badgeClass} border text-xs`}>
            現在: {label}ティア
          </Badge>
        </CardTitle>
      </CardHeader>

      <CardContent className="space-y-4">

        {/* Score headline */}
        <div className="flex items-baseline gap-2 flex-wrap">
          <span className={`text-4xl font-bold tabular-nums ${conf.textColor}`}>{score}</span>
          <span className="text-sm text-muted-foreground">点 / 100点</span>
          {toNext !== null && toNext > 0 && (
            <span className="text-sm text-muted-foreground">
              —&nbsp;<strong className={conf.textColor}>{conf.next}</strong>まであと&nbsp;
              <strong>{toNext}点</strong>
            </span>
          )}
          {toNext !== null && toNext <= 0 && (
            <span className="text-xs text-muted-foreground italic">（次ティア達成済み）</span>
          )}
          {conf.next === null && (
            <span className="text-xs text-amber-600 font-medium">🏆 最高ティア達成</span>
          )}
        </div>

        {/* 3-zone gauge bar */}
        <div className="space-y-1.5">
          {/* Bar */}
          <div className="relative h-6 flex rounded-lg overflow-hidden border border-border/40">

            {/* 梅 zone (0–59): 59% of bar */}
            <div className="relative h-full bg-rose-50" style={{ width: '59%' }}>
              <div
                className="absolute inset-y-0 left-0 bg-rose-400 transition-all duration-700 ease-out"
                style={{ width: umeFill }}
              />
            </div>

            {/* Zone divider */}
            <div className="w-px h-full bg-white/70 shrink-0 z-10" />

            {/* 竹 zone (60–79): 20% of bar */}
            <div className="relative h-full bg-emerald-50" style={{ width: '20%' }}>
              <div
                className="absolute inset-y-0 left-0 bg-emerald-500 transition-all duration-700 ease-out"
                style={{ width: takeFill }}
              />
            </div>

            {/* Zone divider */}
            <div className="w-px h-full bg-white/70 shrink-0 z-10" />

            {/* 松 zone (80–100): 21% of bar */}
            <div className="relative h-full bg-amber-50 flex-1">
              <div
                className="absolute inset-y-0 left-0 bg-amber-400 transition-all duration-700 ease-out"
                style={{ width: matsuFill }}
              />
            </div>

            {/* Score marker line — positioned at score% of total width */}
            <div
              className="absolute top-0 bottom-0 w-0.5 bg-gray-700 z-20"
              style={{ left: `calc(${score}% - 1px)` }}
            />
          </div>

          {/* Zone labels */}
          <div className="flex text-xs text-muted-foreground">
            <div className="flex items-center gap-1" style={{ width: '59%' }}>
              <span className="size-2 rounded-full bg-rose-400 shrink-0" />
              <span>梅 (0–59)</span>
            </div>
            <div className="flex items-center gap-1" style={{ width: '20%' }}>
              <span className="size-2 rounded-full bg-emerald-500 shrink-0" />
              <span>竹 (60–79)</span>
            </div>
            <div className="flex items-center gap-1 flex-1">
              <span className="size-2 rounded-full bg-amber-400 shrink-0" />
              <span>松 (80–100)</span>
            </div>
          </div>
        </div>

        {/* Upgrade items */}
        {data.upgrade_items.length > 0 && toNext !== null && toNext > 0 && (
          <div className="rounded-lg border border-border/50 p-3 space-y-2 bg-muted/30">
            <div className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
              <ArrowUpCircle className="size-3.5" />
              <span>{conf.next}に上げるにはこの項目を追加:</span>
            </div>
            <ul className="space-y-1.5">
              {data.upgrade_items.map((item, idx) => (
                <li key={idx} className="flex items-start gap-2 text-xs">
                  <span className={`mt-0.5 size-1.5 rounded-full shrink-0 ${TIER_CONFIG[conf.next!].dotClass}`} />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Mock notice */}
        {isMock && (
          <p className="text-xs text-muted-foreground/50 italic">
            ※ C06 API（開発中）連携後に実スコアへ切り替わります
          </p>
        )}

      </CardContent>
    </Card>
  );
}
