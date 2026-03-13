import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export interface FarmerProfile {
  id: string; // Supabase auth.users ID
  phone: string;
  name: string;
  dob: string;
  address: string;
  pincode: string;
  email?: string;
}

interface AuthState {
  isAuthenticated: boolean;
  profile: FarmerProfile | null;
  setAuth: (profile: FarmerProfile) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      isAuthenticated: false,
      profile: null,
      setAuth: (profile: FarmerProfile) =>
        set({ isAuthenticated: true, profile }),
      logout: () =>
        set({
          isAuthenticated: false,
          profile: null,
        }),
    }),
    { name: 'arecamitra-supabase-auth' }
  )
);
