import { createNavigationContainerRef } from "@react-navigation/native";
import type { RootStackParamList } from "./AppNavigator";

/**
 * Item 7 — lets `AccountDrawer` (mounted once, outside any individual
 * screen, so it can slide over whichever screen is currently showing)
 * navigate to the Plan screen when a saved plan is tapped, without
 * needing to be a descendant of a particular screen's own navigation
 * prop.
 */
export const navigationRef = createNavigationContainerRef<RootStackParamList>();
