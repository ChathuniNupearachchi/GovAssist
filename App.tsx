import "./global.css";
import { useEffect } from "react";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { AppNavigator } from "./src/navigation/AppNavigator";
import { useDeviceStore } from "./src/store/deviceStore";

export default function App() {
  // Kicked off here, not inside the Services screen, so device-id load +
  // transcript restore (Task 5.3) are already in flight during the
  // Splash/Login screens' own fixed delay — by the time a returning
  // citizen reaches Services, `deviceStore.initializing` has usually
  // already settled. The Services screen still reads that flag itself
  // (loading/error/loaded) rather than assuming it's done.
  useEffect(() => {
    useDeviceStore.getState().initialize();
  }, []);

  return (
    <SafeAreaProvider>
      <AppNavigator />
    </SafeAreaProvider>
  );
}
