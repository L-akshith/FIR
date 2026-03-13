import { create } from 'zustand';

interface ScanResult {
  disease: string;
  confidence: number;
  severity: string | null;
  weather: {
    temperature: number;
    humidity: number;
    wind_speed: number;
    wind_direction: number;
    rainfall_total: number;
  };
  risk_message: string;
  imageUrl?: string;
  timestamp: string;
}

interface AppState {
  recentScans: ScanResult[];
  lastScanResult: ScanResult | null;
  capturedImage: string | null;
  capturedFile: File | null;
  addScan: (scan: ScanResult) => void;
  setLastScanResult: (result: ScanResult | null) => void;
  setCapturedImage: (image: string | null) => void;
  setCapturedFile: (file: File | null) => void;
  clearCapture: () => void;
}

export const useAppStore = create<AppState>((set) => ({
  recentScans: [],
  lastScanResult: null,
  capturedImage: null,
  capturedFile: null,
  addScan: (scan) =>
    set((state) => ({
      recentScans: [scan, ...state.recentScans].slice(0, 20),
    })),
  setLastScanResult: (result) => set({ lastScanResult: result }),
  setCapturedImage: (image) => set({ capturedImage: image }),
  setCapturedFile: (file) => set({ capturedFile: file }),
  clearCapture: () =>
    set({ capturedImage: null, capturedFile: null }),
}));
