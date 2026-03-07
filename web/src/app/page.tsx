'use client';

import { useCallback, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { MainLayout } from '@/components/layout/MainLayout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { useAnalysisStore } from '@/store/analysisStore';
import { uploadPdfAnalysis } from '@/lib/api/client';
import {
  Upload,
  FileText,
  Loader2,
  ChevronDown,
  ChevronUp,
  Search,
  BarChart3,
  Database,
  ArrowRight,
  Shield,
  FlaskConical,
} from 'lucide-react';

const LEVEL_OPTIONS = ['梅', '竹', '松'] as const;

const FEATURES = [
  {
    icon: Search,
    title: '証券コード検索',
    desc: '4桁の証券コードから企業情報を即座に検索',
    href: '/company',
    color: 'text-blue-500',
  },
  {
    icon: BarChart3,
    title: 'ギャップ分析',
    desc: '有報を法令要件と自動照合し、過不足を検出',
    href: '/company',
    color: 'text-green-500',
  },
  {
    icon: FileText,
    title: '松竹梅提案',
    desc: '検出されたギャップに対し3水準の記載文案を生成',
    href: '/company',
    color: 'text-amber-500',
  },
  {
    icon: Database,
    title: 'EDINET連携',
    desc: '金融庁EDINETから有報PDFを直接取得・分析',
    href: '/edinet',
    color: 'text-purple-500',
  },
];

export default function HomePage() {
  const router = useRouter();
  const { setTaskId, addHistory, level, setLevel } = useAnalysisStore();

  const [dragOver, setDragOver] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [companyName, setCompanyName] = useState('');
  const [showDetails, setShowDetails] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFile = useCallback((f: File) => {
    if (!f.name.toLowerCase().endsWith('.pdf')) {
      setError('PDFファイルのみ対応しています');
      return;
    }
    setFile(f);
    setError('');
    // ファイル名から企業名を推測（例: "7203_toyota_2024.pdf" → "toyota"）
    const guessed = f.name.replace(/\.pdf$/i, '').replace(/[_\-\d]+/g, ' ').trim();
    if (!companyName && guessed) setCompanyName(guessed);
  }, [companyName]);

  const onDrop = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      setDragOver(false);
      const f = e.dataTransfer.files[0];
      if (f) handleFile(f);
    },
    [handleFile]
  );

  const onInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const f = e.target.files?.[0];
      if (f) handleFile(f);
    },
    [handleFile]
  );

  const handleAnalyze = async () => {
    if (!file) {
      setError('PDFファイルを選択してください');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const resp = await uploadPdfAnalysis({
        file,
        company_name: companyName,
        level,
        use_mock: true,
      });
      setTaskId(resp.task_id);
      addHistory({
        taskId: resp.task_id,
        companyName: companyName || file.name,
        date: new Date().toLocaleDateString('ja-JP'),
        level,
      });
      router.push('/analysis');
    } catch (e) {
      setError(e instanceof Error ? e.message : '分析開始に失敗しました');
    } finally {
      setLoading(false);
    }
  };

  return (
    <MainLayout>
      <div className="max-w-2xl mx-auto space-y-8">
        {/* Hero */}
        <div className="text-center space-y-2 pt-6">
          <div className="flex items-center justify-center gap-2">
            <Shield className="size-7 text-primary" />
            <h1 className="text-2xl font-bold tracking-tight">開示変更分析システム</h1>
          </div>
          <p className="text-muted-foreground text-sm">
            有報のPDFをドロップするだけで、法令との開示ギャップを自動検出・改善提案まで生成します
          </p>
        </div>

        {/* PDF Drop Zone */}
        <div
          role="button"
          tabIndex={0}
          className={[
            'border-2 border-dashed rounded-xl p-10 text-center cursor-pointer transition-colors',
            dragOver
              ? 'border-primary bg-primary/5'
              : file
              ? 'border-green-500 bg-green-50'
              : 'border-muted-foreground/30 hover:border-primary/60 hover:bg-muted/30',
          ].join(' ')}
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={onDrop}
          onClick={() => inputRef.current?.click()}
          onKeyDown={(e) => e.key === 'Enter' && inputRef.current?.click()}
        >
          <input
            ref={inputRef}
            type="file"
            accept=".pdf,application/pdf"
            className="hidden"
            onChange={onInputChange}
          />
          {file ? (
            <div className="space-y-2">
              <FileText className="size-10 mx-auto text-green-600" />
              <p className="font-medium text-green-700">{file.name}</p>
              <p className="text-xs text-muted-foreground">
                {(file.size / 1024 / 1024).toFixed(1)} MB — クリックで変更
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              <Upload className="size-10 mx-auto text-muted-foreground/60" />
              <div>
                <p className="font-medium">有報PDFをここにドロップ</p>
                <p className="text-xs text-muted-foreground mt-1">
                  または <span className="text-primary underline">クリックして選択</span>
                </p>
              </div>
              <p className="text-xs text-muted-foreground">PDF形式 / 最大20MB</p>
            </div>
          )}
        </div>

        {/* Advanced Settings (collapsible) */}
        <div className="space-y-3">
          <button
            type="button"
            className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors"
            onClick={() => setShowAdvanced((v) => !v)}
          >
            {showAdvanced ? <ChevronUp className="size-4" /> : <ChevronDown className="size-4" />}
            詳細設定
          </button>
          {showAdvanced && (
            <Card>
              <CardContent className="pt-4 space-y-4">
                <div className="space-y-1">
                  <label className="text-sm font-medium">企業名（任意）</label>
                  <input
                    type="text"
                    value={companyName}
                    onChange={(e) => setCompanyName(e.target.value)}
                    placeholder="例: トヨタ自動車"
                    className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-sm font-medium">提案レベル</label>
                  <div className="flex gap-2">
                    {LEVEL_OPTIONS.map((l) => (
                      <button
                        key={l}
                        type="button"
                        onClick={() => setLevel(l)}
                        className={[
                          'px-4 py-1.5 rounded-full text-sm border transition-colors',
                          level === l
                            ? 'border-primary bg-primary text-primary-foreground'
                            : 'border-input hover:border-primary/60',
                        ].join(' ')}
                      >
                        {l}
                      </button>
                    ))}
                  </div>
                  <p className="text-xs text-muted-foreground">
                    梅: コンパクト / 竹: 標準（推奨） / 松: 詳細
                  </p>
                </div>
              </CardContent>
            </Card>
          )}
        </div>

        {/* Error */}
        {error && (
          <div className="rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
            {error}
          </div>
        )}

        {/* CTA */}
        <Button
          size="lg"
          className="w-full"
          onClick={handleAnalyze}
          disabled={loading || !file}
        >
          {loading ? (
            <>
              <Loader2 className="size-4 animate-spin" />
              分析起動中...
            </>
          ) : (
            '分析開始'
          )}
        </Button>

        {/* Sample link */}
        <div className="flex items-center justify-center gap-1.5">
          <Button
            variant="outline"
            size="sm"
            className="gap-1.5 text-amber-700 border-amber-300 hover:bg-amber-50"
            onClick={() => router.push('/sample')}
          >
            <FlaskConical className="size-3.5" />
            サンプルレポートを見る（30秒で成果物確認）
          </Button>
        </div>

        {/* Alt: stock code search */}
        <p className="text-center text-sm text-muted-foreground">
          PDFをお持ちでない場合は{' '}
          <button
            type="button"
            className="text-primary underline hover:no-underline"
            onClick={() => router.push('/company')}
          >
            証券コードで検索
          </button>{' '}
          または{' '}
          <button
            type="button"
            className="text-primary underline hover:no-underline"
            onClick={() => router.push('/edinet')}
          >
            EDINETから取得
          </button>
        </p>

        {/* Divider + Feature Cards (secondary info) */}
        <div>
          <button
            type="button"
            className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors mx-auto"
            onClick={() => setShowDetails((v) => !v)}
          >
            {showDetails ? <ChevronUp className="size-4" /> : <ChevronDown className="size-4" />}
            詳細・機能説明
          </button>

          {showDetails && (
            <div className="mt-4 space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {FEATURES.map((f) => (
                  <Card
                    key={f.title}
                    className="cursor-pointer hover:shadow-md transition-shadow"
                    onClick={() => router.push(f.href)}
                  >
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2 text-base">
                        <f.icon className={`size-4 ${f.color}`} />
                        {f.title}
                      </CardTitle>
                      <CardDescription className="text-xs">{f.desc}</CardDescription>
                    </CardHeader>
                    <CardContent>
                      <Button variant="ghost" size="sm" className="gap-1 text-xs">
                        開始 <ArrowRight className="size-3" />
                      </Button>
                    </CardContent>
                  </Card>
                ))}
              </div>

              {/* Pipeline */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">処理フロー</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="flex flex-wrap items-center gap-2 text-sm">
                    {['読取', '照合', '分析', '提案作成', 'レポート生成'].map((label, i) => (
                      <div key={label} className="flex items-center gap-2">
                        {i > 0 && <ArrowRight className="size-3 text-muted-foreground" />}
                        <div className="bg-muted px-3 py-1.5 rounded-full text-xs">
                          {label}
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>

              <div className="flex flex-wrap items-center justify-center gap-2 pb-4">
                <Badge variant="secondary">Phase 2 完了</Badge>
                <Badge variant="outline">408テストPASS</Badge>
              </div>
            </div>
          )}
        </div>
      </div>
    </MainLayout>
  );
}
