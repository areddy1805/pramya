// Active career profile — persisted UX preference.
// The backend (user.active_profile_id) is authoritative; this store mirrors
// it for instant UI switching and survives reload via localStorage. It is
// NEVER an authorization boundary: every API call still sends an explicit
// profile_id that the backend verifies against the authenticated user.

import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export const ACTIVE_PROFILE_KEY = 'pramya-active-profile'

interface ProfileState {
  activeProfileId: number | null
  userId: number | null
  setActiveProfile: (userId: number, profileId: number) => void
  clear: () => void
}

export const useProfileStore = create<ProfileState>()(
  persist(
    (set) => ({
      activeProfileId: null,
      userId: null,
      setActiveProfile: (userId, profileId) => set({ userId, activeProfileId: profileId }),
      clear: () => set({ userId: null, activeProfileId: null }),
    }),
    { name: ACTIVE_PROFILE_KEY },
  ),
)
