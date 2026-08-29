import "./global.css";
import { useEffect } from "react";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { AppNavigator } from "./src/navigation/AppNavigator";
import { AccountDrawer } from "./src/components/AccountDrawer";
import { useDeviceStore } from "./src/store/deviceStore";
import { useAuthStore } from "./src/store/authStore";

export default function App() {
  // Kicked off here, not inside the Services screen, so device-id load +
  // transcript restore (Task 5.3) are already in flight during the
  // Splash/Login screens' own fixed delay — by the time a returning
  // citizen reaches Services, `deviceStore.initializing` has usually
  // already settled. The Services screen still reads that flag itself
  // (loading/error/loaded) rather than assuming it's done.
  useEffect(() => {
    useDeviceStore.getState().initialize();
    // Item 7 — restores a persisted sign-in on launch, entirely
    // independent of deviceStore's own init: an anonymous citizen's
    // case is never touched by whether this finds a stored token.
    useAuthStore.getState().initialize();
  }, []);

  return (
    <SafeAreaProvider>
      <AppNavigator />
      <AccountDrawer />
    </SafeAreaProvider>
  );
}
