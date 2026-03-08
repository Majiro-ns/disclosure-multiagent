'use client';

import { useState, useCallback, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { MainLayout } from '@/components/layout/MainLayout';
import { Button } from '@/components/ui/button';
import { useAnalysisStore } from '@/store/analysisStore';
import { executeNextStep, runAllRemaining } from '@/lib/api/client';
import { M1Output } from '@/components/step/M1Output';
import { M2Output } from '@/components/step/M2Output';
import { M3Output } from '@/components/step/M3Output';
import { M4Output } from '@/components/step/M4Output';
import { M5Output } from '@/components/step/M5Output';
import type {
  StepOutputsMap,
  M1StepOutput,
  M2StepOutput,
  M3StepOutput,
  M4StepOutput,
  M5StepOutput,
} from '@/types';
import { CheckCircle2, Circle, Loader2, ArrowRight, Play, RotateCcw } from 'lucide-react';

const STAGES: { key: keyof StepOutputsMap; label: string; shortLabel: string }[] = [
  { key: 'm1', label: 'M1: PDF解析', shortLabel: 'M1' },
  { key: 'm2', label: 'M2: 法令取得', shortLabel: 'M2' },
  { key: 'm3', label: 'M3: ギャップ分析', shortLabel: 'M3' },
  { key: 'm4', label: 'M4: 提案生成', shortLabel: 'M4' },
  { key: 'm5', label: 'M5: レポート', shortLabel: 'M5' },
];

export default function StepAnalysisPage() {
  const router = useRouter();
  const { stepTaskId, stepOutputs, setStepOutput } = useAnalysisStore();

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [waitingDebug, setWaitingDebug] = useState(false);
  const [allDone, setAllDone] = useState(false);
  const [activeStage, setActiveStage] = useState<keyof StepOutputsMap>('m1');

  // Detect first completed stage to display
  useEffect(() => {
    const last = [...STAGES].reverse().find((s) => stepOutputs[s.key]);
    if (last) setActiveStage(last.key);
  }, [stepOutputs]);

  // Detect all-done when all 5 stages filled
  useEffect(() => {
    if (STAGES.every((s) => stepOutputs[s.key])) setAllDone(true);
  }, [stepOutputs]);

  const nextStageIndex = STAGES.findIndex((s) => !stepOutputs[s.key]);
  const nextStage = nextStageIndex >= 0 ? STAGES[nextStageIndex] : null;

  const handleNextStep = useCallback(async () => {
    if (!stepTaskId) return;
    setLoading(true);
    setError('');
    setWaitingDebug(false);
    try {
      const resp = await executeNextStep(stepTaskId);
      if (resp.output) {
        setStepOutput(resp.step, resp.output);
        setActiveStage(resp.step);
      }
      if (resp.status === 'waiting_debug') {
        setWaitingDebug(true);
      } else if (resp.status === 'all_done') {
        setAllDone(true);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : '実行に失敗しました');
    } finally {
      setLoading(false);
    }
  }, [stepTaskId, setStepOutput]);

  const handleRunAll = useCallback(async () => {
    if (!stepTaskId) return;
    setLoading(true);
    setError('');
    try {
      await runAllRemaining(stepTaskId);
      router.push(`/report/${stepTaskId}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : '一括実行に失敗しました');
      setLoading(false);
    }
  }, [stepTaskId, router]);

  if (!stepTaskId) {
    return (
      <MainLayout>
        <div className="max-w-3xl mx-auto text-center py-12 space-y-4">
          <p className="text-muted-foreground">ステップ実行タスクが見つかりません</p>
          <Button onClick={() => router.push('/')}>トップに戻る</Button>
        </div>
      </MainLayout>
    );
  }

  const activeOutput = stepOutputs[activeStage];

  return (
    <MainLayout>
      <div className="max-w-5xl mx-auto space-y-4">
        {/* Header */}
        <div>
          <h1 className="text-xl font-bold">ステップ実行モード</h1>
          <p className="text-xs text-muted-foreground mt-0.5">Task ID: {stepTaskId}</p>
        </div>

        {/* Main Panel */}
        <div className="flex gap-4" style={{ minHeight: '520px' }}>
          {/* Left: Stage List */}
          <div className="w-44 shrink-0 space-y-1.5">
            {STAGES.map((stage, i) => {
              const isDone = !!stepOutputs[stage.key];
              const isActive = activeStage === stage.key;
              const isRunning = !isDone && nextStageIndex === i && loading;
              return (
                <button
                  key={stage.key}
                  type="button"
                  disabled={!isDone}
                  onClick={() => { if (isDone) setActiveStage(stage.key); }}
                  className={[
                    'w-full flex items-center gap-2 px-3 py-2 rounded-lg border text-sm transition-colors text-left',
                    isActive && isDone
                      ? 'border-primary bg-primary/5 font-medium'
                      : isDone
                      ? 'border-green-500/50 bg-green-50 hover:border-green-500 cursor-pointer'
                      : 'border-input bg-muted/30 text-muted-foreground cursor-default',
                  ].join(' ')}
                >
                  {isRunning ? (
                    <Loader2 className="size-4 text-primary animate-spin shrink-0" />
                  ) : isDone ? (
                    <CheckCircle2 className={`size-4 shrink-0 ${isActive ? 'text-primary' : 'text-green-600'}`} />
                  ) : (
                    <Circle className="size-4 text-muted-foreground/40 shrink-0" />
                  )}
                  <span className="truncate">{stage.label}</span>
                </button>
              );
            })}
          </div>

          {/* Right: Output + Actions */}
          <div className="flex-1 min-w-0 flex flex-col gap-3">
            {/* Debug waiting banner */}
            {waitingDebug && (
              <div className="flex items-center gap-2 px-3 py-2 rounded-lg border border-amber-300 bg-amber-50 text-amber-700 text-sm">
                <Loader2 className="size-4 animate-spin shrink-0" />
                <span>足軽応答待ち — 足軽がLLM処理を完了次第、次のステップへ進めます</span>
              </div>
            )}

            {/* Output Area */}
            <div className="flex-1 border rounded-lg p-4 overflow-auto bg-background">
              {activeOutput ? (
                <div className="space-y-2">
                  <p className="text-xs font-medium text-muted-foreground">
                    {STAGES.find((s) => s.key === activeStage)?.label} — 出力
                  </p>
                  {activeStage === 'm1' && <M1Output data={activeOutput as M1StepOutput} />}
                  {activeStage === 'm2' && <M2Output data={activeOutput as M2StepOutput} />}
                  {activeStage === 'm3' && <M3Output data={activeOutput as M3StepOutput} />}
                  {activeStage === 'm4' && <M4Output data={activeOutput as M4StepOutput} />}
                  {activeStage === 'm5' && <M5Output data={activeOutput as M5StepOutput} />}
                </div>
              ) : (
                <div className="h-full flex flex-col items-center justify-center gap-2 text-center text-muted-foreground">
                  <Circle className="size-8 text-muted-foreground/30" />
                  <p className="text-sm">「次のステップへ」を押すと出力が表示されます</p>
                </div>
              )}
            </div>

            {/* Error */}
            {error && (
              <div className="rounded-md border border-destructive/50 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                {error}
              </div>
            )}

            {/* Action Buttons */}
            {allDone ? (
              <Button size="lg" onClick={() => router.push(`/report/${stepTaskId}`)}>
                レポートを表示 <ArrowRight className="size-4" />
              </Button>
            ) : (
              <div className="flex items-center gap-2">
                <Button
                  onClick={handleNextStep}
                  disabled={loading || waitingDebug}
                  className="gap-1.5"
                >
                  {loading ? (
                    <><Loader2 className="size-4 animate-spin" />実行中...</>
                  ) : (
                    <><Play className="size-4" />次のステップへ{nextStage ? ` (${nextStage.shortLabel})` : ''}</>
                  )}
                </Button>
                <Button
                  variant="outline"
                  onClick={handleRunAll}
                  disabled={loading}
                  className="gap-1.5"
                >
                  残り全実行
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => router.push('/')}
                  disabled={loading}
                  className="ml-auto text-muted-foreground gap-1.5"
                >
                  <RotateCcw className="size-3" />
                  最初から
                </Button>
              </div>
            )}
          </div>
        </div>
      </div>
    </MainLayout>
  );
}
