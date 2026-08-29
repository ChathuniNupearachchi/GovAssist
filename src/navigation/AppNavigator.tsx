import { NavigationContainer } from "@react-navigation/native";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import { colors, fontSize } from "../theme/tokens";
import { SplashScreen } from "../screens/SplashScreen";
import { LoginScreen } from "../screens/LoginScreen";
import { DepartmentsScreen } from "../screens/DepartmentsScreen";
import { ServicesScreen } from "../screens/ServicesScreen";
import { PlanScreen } from "../screens/PlanScreen";
import { UserMenuButton } from "../components/UserMenuButton";
import { navigationRef } from "./navigationRef";

export type RootStackParamList = {
  Splash: undefined;
  Login: undefined;
  Departments: undefined;
  Services: { initialTab?: "services" | "ask" } | undefined;
  Plan: undefined;
};

const Stack = createNativeStackNavigator<RootStackParamList>();

export function AppNavigator() {
  return (
    <NavigationContainer ref={navigationRef}>
      <Stack.Navigator
        initialRouteName="Splash"
        screenOptions={{
          headerStyle: { backgroundColor: colors.surface },
          headerShadowVisible: false,
          headerTintColor: colors.primary,
          headerTitleStyle: { fontSize: fontSize.title, fontWeight: "700", color: colors.textPrimary },
          headerBackTitle: "Back",
          contentStyle: { backgroundColor: colors.background },
          // Item 7 — a user icon on every main screen; Splash/Login have
          // no header at all, so this only ever renders on the three
          // screens below.
          headerRight: () => <UserMenuButton />,
        }}
      >
        <Stack.Screen name="Splash" component={SplashScreen} options={{ headerShown: false }} />
        <Stack.Screen name="Login" component={LoginScreen} options={{ headerShown: false }} />
        <Stack.Screen name="Departments" component={DepartmentsScreen} options={{ title: "Departments" }} />
        <Stack.Screen
          name="Services"
          component={ServicesScreen}
          options={{ title: "Immigration & Emigration" }}
        />
        <Stack.Screen name="Plan" component={PlanScreen} options={{ title: "Your Plan" }} />
      </Stack.Navigator>
    </NavigationContainer>
  );
}
