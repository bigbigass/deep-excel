import { InvestigationWorkspace } from "@/components/investigation-workspace";

export default async function InvestigationPage({
  params
}: {
  params: Promise<{ caseId: string }>;
}) {
  const { caseId } = await params;
  return <InvestigationWorkspace caseId={caseId} />;
}
