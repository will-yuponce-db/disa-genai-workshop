import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/Card";

export default function Charts() {
  return (
    <div className="space-y-4 max-w-4xl">
      <Card>
        <CardHeader>
          <CardTitle>Vibe-coded charts go here</CardTitle>
          <CardDescription>
            Live demo: paste Genie SQL into <code className="text-blue-400">prompts/vibe_code_component.md</code>, get a React file back, drop it in <code className="text-blue-400">src/pages/</code>, and add a route.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-slate-400">
            During the workshop, this page is empty. As we vibe-code, components will appear here.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
