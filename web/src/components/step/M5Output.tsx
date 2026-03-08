'use client';

import type { M5StepOutput } from '@/types';
import { ReportViewer } from '@/components/report/ReportViewer';

interface Props {
  data: M5StepOutput;
}

export function M5Output({ data }: Props) {
  return (
    <div className="max-h-[460px] overflow-y-auto rounded border p-4">
      <ReportViewer markdown={data.report_markdown} />
    </div>
  );
}
