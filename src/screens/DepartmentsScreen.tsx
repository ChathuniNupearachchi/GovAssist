import { ScrollView, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import type { RootStackParamList } from "../navigation/AppNavigator";
import { DepartmentCard } from "../components/DepartmentCard";
import { colors, spacing, fontSize } from "../theme/tokens";

type Props = NativeStackScreenProps<RootStackParamList, "Departments">;

export function DepartmentsScreen({ navigation }: Props) {
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.background }} edges={["bottom", "left", "right"]}>
      <ScrollView contentContainerStyle={{ padding: spacing.md, gap: spacing.md }}>
        <View style={{ marginBottom: spacing.sm }}>
          <Text style={{ fontSize: fontSize.body, color: colors.textSecondary }}>
            Choose a department to get started.
          </Text>
        </View>

        <DepartmentCard
          title="Immigration & Emigration"
          subtitle="Passports, visas & travel documents"
          icon="earth-outline"
          status="available"
          onPress={() => navigation.navigate("Services")}
        />

        <DepartmentCard
          title="Department of Motor Traffic"
          subtitle="Vehicle registration & driving licences"
          icon="car-outline"
          status="comingSoon"
        />

        <DepartmentCard
          title="Registrar General"
          subtitle="Births, deaths & marriage certificates"
          icon="document-text-outline"
          status="comingSoon"
        />

        <DepartmentCard
          title="Registration of Persons"
          subtitle="National Identity Cards"
          icon="card-outline"
          status="comingSoon"
        />
      </ScrollView>
    </SafeAreaView>
  );
}
