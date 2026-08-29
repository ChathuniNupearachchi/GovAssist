import { create } from "zustand";
import { getStudios, postResolve, UnexpectedResponseError } from "../api/client";
import type { NetworkError, ServerError, UnreachableError } from "../api/errors";
import type { CaseResolution, StudioResolution } from "../api/types";

export type PlanFetchError = NetworkError | UnreachableError | ServerError | UnexpectedResponseError;

function isPlanFetchError(error: unknown): error is PlanFetchError {
  return (
    error instanceof Error &&
    (error.name === "NetworkError" ||
      error.name === "UnreachableError" ||
      error.name === "ServerError" ||
      error.name === "UnexpectedResponseError")
  );
}

type PlanState = {
  resolution: CaseResolution | null;
  /** Set from a 409's body when intake isn't complete yet — the citizen still has a question to answer before a plan exists. */
  pendingQuestion: string | null;
  resolveLoading: boolean;
  resolveError: PlanFetchError | null;

  studios: StudioResolution | null;
  studiosLoading: boolean;
  studiosError: PlanFetchError | null;

  resolveCase: (caseId: string) => Promise<void>;
  loadStudios: (district: string) => Promise<void>;
  reset: () => void;
};

const INITIAL_STATE = {
  resolution: null,
  pendingQuestion: null,
  resolveLoading: false,
  resolveError: null,

  studios: null,
  studiosLoading: false,
  studiosError: null,
} as const;

export const usePlanStore = create<PlanState>((set) => ({
  ...INITIAL_STATE,

  resolveCase: async (caseId: string) => {
    set({ resolveLoading: true, resolveError: null });
    try {
      const result = await postResolve(caseId);
      if (result.ready) {
        set({ resolution: result.resolution, pendingQuestion: null, resolveLoading: false });
      } else {
        set({ resolution: null, pendingQuestion: result.pendingQuestion, resolveLoading: false });
      }
    } catch (error) {
      if (isPlanFetchError(error)) {
        set({ resolveLoading: false, resolveError: error });
      } else {
        set({ resolveLoading: false });
        throw error;
      }
    }
  },

  loadStudios: async (district: string) => {
    set({ studiosLoading: true, studiosError: null });
    try {
      const studios = await getStudios(district);
      set({ studios, studiosLoading: false });
    } catch (error) {
      if (isPlanFetchError(error)) {
        set({ studiosLoading: false, studiosError: error });
      } else {
        set({ studiosLoading: false });
        throw error;
      }
    }
  },

  reset: () => set({ ...INITIAL_STATE }),
}));
