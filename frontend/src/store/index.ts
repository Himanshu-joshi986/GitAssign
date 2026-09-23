import { configureStore } from '@reduxjs/toolkit'
import { api } from './apiSlice'
import uiReducer from './uiSlice'

export const store = configureStore({
  reducer: {
    [api.reducerPath]: api.reducer,
    ui: uiReducer,
  },
  middleware: (getDefault) => getDefault().concat(api.middleware),
})

export type RootState   = ReturnType<typeof store.getState>
export type AppDispatch = typeof store.dispatch
