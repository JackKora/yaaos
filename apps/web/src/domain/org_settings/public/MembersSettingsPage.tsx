import { MembersPage } from "../MembersPage";
import { OrgSettingsLayout } from "../OrgSettingsLayout";

export function MembersSettingsPage() {
  return (
    <OrgSettingsLayout active="members">
      <MembersPage />
    </OrgSettingsLayout>
  );
}
