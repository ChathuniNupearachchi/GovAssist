# GovAssist

React Native (Expo SDK 54) mobile app for Sri Lankan government services.

Takes a citizen's specific situation, resolves it against verified government rules,
and produces a personalised document checklist — with the source and verified date
on every requirement. Not a chatbot: the output is a plan the user can act on.

First department: Department of Immigration & Emigration (passports).
Later: Registration of Persons, Registrar General, Motor Traffic.
English only for this build.

## Stack

- React Native + Expo SDK 54, TypeScript strict
- NativeWind v4 (Tailwind v3 — not v4)
- React Navigation (native stack)
- Zustand for state
- Backend: FastAPI + PostgreSQL/pgvector (separate repo)

## Rules

- React Native only. No web APIs, no DOM, no `div`/`span`. Use `View`, `Text`, `Pressable`.
- Never pass a function to `style`. NativeWind does not apply it. Use a plain object and
  track pressed state with `onPressIn`/`onPressOut` + `useState`.
- Do not combine `className` with a `style` function on the same element. Prefer `style`.
- All colours, spacing, radii and font sizes come from `src/theme/tokens.ts`. Never hardcode.
- Minimum touch target 48px (`touchTarget.min`). Minimum body font size 16px.
- Every interactive element needs `accessibilityRole` and `accessibilityLabel`.
  Checkboxes and toggles also need `accessibilityState`.
- Component variants are string unions with a lookup object, not boolean props.
  Good: `variant?: "primary" | "secondary"`. Bad: `isPrimary?: boolean`.
- TypeScript strict. No `any`.
- Every data surface handles four states: loading, empty, error, loaded.
- Export new components from `src/components/index.ts`.

## Structure

src/components reusable primitives (Button, Card, ChecklistItem)
src/screens full screens
src/navigation React Navigation stack
src/theme tokens.ts — single source of truth for design values
src/api backend client
src/store Zustand stores

## Users

Sri Lankan citizens, including older and less technical people, often anxious about a
government process and using the app on a phone outdoors. Plain language, no jargon,
generous spacing, high contrast.

## Content rules

- Every requirement shown to a user must carry its source and a verified-as-of date.
- Never state a fee, document or deadline that did not come from the rules API.
- The app gives guidance, not an official ruling. Say so where it matters.
