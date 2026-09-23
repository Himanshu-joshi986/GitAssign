import { createSlice, PayloadAction } from '@reduxjs/toolkit'
import type { RootState } from './index'

interface UiState {
  activeRepo:      string
  selectedIssue:   number | null
  checkedIssues:   number[]
  activeTab:       'issues' | 'assign' | 'metrics' | 'developers' | 'demo'
  assignResults:   any[]
  notification:    { message: string; type: 'success' | 'error' | 'info' } | null
}

const initialState: UiState = {
  activeRepo:    '',
  selectedIssue: null,
  checkedIssues: [],
  activeTab:     'issues',
  assignResults: [],
  notification:  null,
}

const uiSlice = createSlice({
  name: 'ui',
  initialState,
  reducers: {
    setRepo(state, action: PayloadAction<string>) {
      state.activeRepo    = action.payload
      state.selectedIssue = null
      state.checkedIssues = []
      state.assignResults = []
    },
    selectIssue(state, action: PayloadAction<number | null>) {
      state.selectedIssue = action.payload
    },
    toggleChecked(state, action: PayloadAction<number>) {
      const num = action.payload
      const idx = state.checkedIssues.indexOf(num)
      if (idx >= 0) state.checkedIssues.splice(idx, 1)
      else          state.checkedIssues.push(num)
    },
    clearChecked(state) {
      state.checkedIssues = []
    },
    checkAll(state, action: PayloadAction<number[]>) {
      state.checkedIssues = action.payload
    },
    setTab(state, action: PayloadAction<UiState['activeTab']>) {
      state.activeTab = action.payload
    },
    setAssignResults(state, action: PayloadAction<any[]>) {
      state.assignResults = action.payload
    },
    notify(state, action: PayloadAction<UiState['notification']>) {
      state.notification = action.payload
    },
    clearNotification(state) {
      state.notification = null
    },
  },
})

export const {
  setRepo, selectIssue, toggleChecked, clearChecked,
  checkAll, setTab, setAssignResults, notify, clearNotification,
} = uiSlice.actions

export const selectActiveRepo    = (s: RootState) => s.ui.activeRepo
export const selectSelectedIssue = (s: RootState) => s.ui.selectedIssue
export const selectCheckedIssues = (s: RootState) => s.ui.checkedIssues
export const selectActiveTab     = (s: RootState) => s.ui.activeTab
export const selectAssignResults = (s: RootState) => s.ui.assignResults
export const selectNotification  = (s: RootState) => s.ui.notification

export default uiSlice.reducer
