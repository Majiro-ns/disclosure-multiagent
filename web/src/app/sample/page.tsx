'use client';

import { MainLayout } from '@/components/layout/MainLayout';
import { GapSummaryCard } from '@/components/analysis/GapSummaryCard';
import { GapTable } from '@/components/analysis/GapTable';
import { ProposalCard } from '@/components/analysis/ProposalCard';
import { ReportViewer } from '@/components/report/ReportViewer';
import { ExportButtons } from '@/components/report/ExportButtons';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { Button, buttonVariants } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { useRouter } from 'next/navigation';
import { ArrowLeft, ArrowRight, Download, FileText, FlaskConical, Upload } from 'lucide-react';
import type { AnalysisResult } from '@/types';
import sampleData from '../../../public/sample_report.json';

const result = sampleData as AnalysisResult;

export default function SamplePage() {
  const router = useRouter();
  const gapsWithGap = result.gaps.filter((g) => g.has_gap);

  return (
    <MainLayout>
      <div className="max-w-5xl mx-auto space-y-6">
        {/* サンプル注記バナー */}
        <div className="flex items-start gap-3 rounded-lg border border-amber-400/60 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          <FlaskConical className="size-4 mt-0.5 shrink-0" />
          <div>
            <span className="font-semibold">サンプルデータです。</span>
            架空の企業「株式会社テスト商事」のデータを使用しています。実際の分析は有報PDFをアップロードして行ってください。
          </div>
        </div>

        {/* 今すぐ試してみよう — 初回ユーザー向けガイド */}
        <Card className="border-primary/40 bg-primary/3">
          <CardHeader className="pb-2">
            <CardTitle className="text-base flex items-center gap-2">
              <FileText className="size-4 text-primary" />
              このサンプルPDFで今すぐ試せます（APIキー不要）
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm text-muted-foreground">
              下のサンプルPDFは分析デモ用の架空有報です。ダウンロードしてトップページにドロップするだけで、分析フルフローを体験できます。
            </p>
            <ol className="text-sm space-y-1 list-decimal list-inside text-muted-foreground">
              <li>
                <span className="font-medium text-foreground">PDFをダウンロード</span>
                （株式会社テスト商事 2024年度 有価証券報告書・架空）
              </li>
              <li>
                <span className="font-medium text-foreground">トップページへ移動</span>してPDFをドロップ
              </li>
              <li>「分析開始」ボタンをクリック — <span className="font-medium text-foreground">約5秒</span>で結果表示</li>
            </ol>
            <div className="flex flex-wrap gap-2 pt-1">
              <a
                href="/sample_yuho.pdf"
                download="sample_yuho_テスト商事.pdf"
                className={cn(buttonVariants({ variant: 'default', size: 'sm' }), 'gap-1.5')}
              >
                <Download className="size-3.5" />
                サンプルPDFをダウンロード
              </a>
              <Button
                variant="outline"
                size="sm"
                className="gap-1.5"
                onClick={() => router.push('/')}
              >
                <Upload className="size-3.5" />
                PDFをアップロードして分析
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* ヘッダー */}
        <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold">{result.company_name}</h1>
            <div className="flex items-center gap-2 mt-1">
              <Badge variant="secondary">{result.fiscal_year}年度</Badge>
              <Badge variant="outline">提案レベル: {result.level}</Badge>
              <Badge variant="outline" className="bg-amber-100 text-amber-700 border-amber-300">
                サンプル
              </Badge>
            </div>
          </div>
          <div className="flex gap-2 flex-wrap">
            <ExportButtons markdown={result.report_markdown} companyName={result.company_name} />
            <Button variant="outline" size="sm" onClick={() => router.push('/')}>
              <ArrowLeft className="size-3" />
              トップへ戻る
            </Button>
          </div>
        </div>

        {/* タブ */}
        <Tabs defaultValue="summary">
          <TabsList className="flex-wrap h-auto">
            <TabsTrigger value="summary">サマリ</TabsTrigger>
            <TabsTrigger value="gaps">ギャップ ({gapsWithGap.length})</TabsTrigger>
            <TabsTrigger value="proposals">改善提案 ({result.proposals.length})</TabsTrigger>
            <TabsTrigger value="report">全文レポート</TabsTrigger>
          </TabsList>

          {/* サマリ */}
          <TabsContent value="summary">
            <div className="space-y-4">
              <GapSummaryCard summary={result.summary} />
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <Card>
                  <CardContent className="pt-4 text-center">
                    <div className="text-2xl font-bold">{result.gaps.length}</div>
                    <div className="text-xs text-muted-foreground">分析項目</div>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="pt-4 text-center">
                    <div className="text-2xl font-bold text-red-600">{gapsWithGap.length}</div>
                    <div className="text-xs text-muted-foreground">ギャップあり</div>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="pt-4 text-center">
                    <div className="text-2xl font-bold text-green-600">
                      {result.no_gap_items.length}
                    </div>
                    <div className="text-xs text-muted-foreground">充足済み</div>
                  </CardContent>
                </Card>
              </div>
            </div>
          </TabsContent>

          {/* ギャップ一覧 */}
          <TabsContent value="gaps">
            <Card>
              <CardHeader>
                <CardTitle>ギャップ一覧</CardTitle>
              </CardHeader>
              <CardContent>
                <GapTable gaps={result.gaps} />
              </CardContent>
            </Card>
          </TabsContent>

          {/* 改善提案 */}
          <TabsContent value="proposals">
            <ProposalCard proposals={result.proposals} />
          </TabsContent>

          {/* 全文レポート */}
          <TabsContent value="report">
            <Card>
              <CardContent className="pt-6">
                <ReportViewer markdown={result.report_markdown} />
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>

        {/* 実際に使うCTA */}
        <Card className="border-primary/30 bg-primary/5">
          <CardContent className="pt-6">
            <div className="text-center space-y-3">
              <p className="font-semibold">自社の有報で試してみましょう</p>
              <p className="text-sm text-muted-foreground">
                PDFをアップロードするだけ。APIキー不要のモックモードで即試せます。
              </p>
              <div className="flex flex-wrap gap-3 justify-center">
                <Button size="lg" onClick={() => router.push('/')} className="gap-1.5">
                  <Upload className="size-4" />
                  PDFをアップロードして分析
                </Button>
                <Button size="lg" variant="outline" onClick={() => router.push('/company')} className="gap-1.5">
                  証券コードで検索
                  <ArrowRight className="size-4" />
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </MainLayout>
  );
}
