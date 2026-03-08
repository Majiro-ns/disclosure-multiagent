import { create } from 'zustand';
import type { CompanyInfo, PipelineStatus, AnalysisResult, StepOutputsMap } from '@/types';

interface AnalysisState {
  // Search
  selectedCompany: CompanyInfo | null;
  setSelectedCompany: (company: CompanyInfo | null) => void;

  // Analysis params
  fiscalYear: number;
  setFiscalYear: (year: number) => void;
  fiscalMonthEnd: number;
  setFiscalMonthEnd: (month: number) => void;
  level: '松' | '竹' | '梅';
  setLevel: (level: '松' | '竹' | '梅') => void;

  // Pipeline (auto mode)
  taskId: string | null;
  setTaskId: (id: string | null) => void;
  pipelineStatus: PipelineStatus | null;
  setPipelineStatus: (status: PipelineStatus | null) => void;

  // Result
  result: AnalysisResult | null;
  setResult: (result: AnalysisResult | null) => void;

  // Step execution mode
  stepTaskId: string | null;
  setStepTaskId: (id: string | null) => void;
  stepOutputs: StepOutputsMap;
  setStepOutput: (stage: keyof StepOutputsMap, data: StepOutputsMap[keyof StepOutputsMap]) => void;
  clearStepOutputs: () => void;

  // History
  history: { taskId: string; companyName: string; date: string; level: string }[];
  addHistory: (entry: { taskId: string; companyName: string; date: string; level: string }) => void;

  // Reset
  reset: () => void;
}

export const useAnalysisStore = create<AnalysisState>((set) => ({
  selectedCompany: null,
  setSelectedCompany: (company) => set({ selectedCompany: company }),

  fiscalYear: 2025,
  setFiscalYear: (year) => set({ fiscalYear: year }),
  fiscalMonthEnd: 3,
  setFiscalMonthEnd: (month) => set({ fiscalMonthEnd: month }),
  level: '竹',
  setLevel: (level) => set({ level }),

  taskId: null,
  setTaskId: (id) => set({ taskId: id }),
  pipelineStatus: null,
  setPipelineStatus: (status) => set({ pipelineStatus: status }),

  result: null,
  setResult: (result) => set({ result }),

  stepTaskId: null,
  setStepTaskId: (id) => set({ stepTaskId: id }),
  stepOutputs: {},
  setStepOutput: (stage, data) =>
    set((state) => ({ stepOutputs: { ...state.stepOutputs, [stage]: data } })),
  clearStepOutputs: () => set({ stepOutputs: {}, stepTaskId: null }),

  history: [],
  addHistory: (entry) => set((state) => ({ history: [entry, ...state.history].slice(0, 20) })),

  reset: () =>
    set({
      selectedCompany: null,
      taskId: null,
      pipelineStatus: null,
      result: null,
      stepTaskId: null,
      stepOutputs: {},
    }),
}));
