import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/Card";

export default function Home() {
  return (
    <div className="space-y-4 max-w-3xl">
      <h1 className="text-2xl font-bold">DISA Cyber Threat Intelligence</h1>
      <p className="text-slate-400">
        Compound AI agent over CISA advisories, KEV catalog, NVD CVEs, MITRE ATT&amp;CK, and DoD STIGs.
      </p>
      <div className="grid grid-cols-2 gap-4">
        <Card>
          <CardHeader>
            <CardTitle>Active KEV count</CardTitle>
            <CardDescription>Last 30 days</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">—</div>
            <p className="text-xs text-slate-500 mt-2">Ask the assistant: "How many KEV-listed CVEs were added in the last 30 days?"</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Exposed assets</CardTitle>
            <CardDescription>Hosts running KEV-affected products</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">—</div>
            <p className="text-xs text-slate-500 mt-2">Ask: "Show me SIPRNet hosts exposed to KEV vulnerabilities."</p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
