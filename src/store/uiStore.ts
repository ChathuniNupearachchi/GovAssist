import { create } from "zustand";

/** Item 7 — the account drawer's open/closed state, kept separate from
 * `authStore`/`deviceStore` since it's pure UI state with no server or
 * persisted-storage dimension. */
type UIState = {
  isDrawerOpen: boolean;
  openDrawer: () => void;
  closeDrawer: () => void;
};

export const useUIStore = create<UIState>((set) => ({
  isDrawerOpen: false,
  openDrawer: () => set({ isDrawerOpen: true }),
  closeDrawer: () => set({ isDrawerOpen: false }),
}));
