import RenderPreview from "./render-preview";

export default async function ReviewRevisionPage({
  params,
}: {
  params: Promise<{ revisionId: string }>;
}) {
  const { revisionId } = await params;
  return <RenderPreview revisionId={revisionId} />;
}
