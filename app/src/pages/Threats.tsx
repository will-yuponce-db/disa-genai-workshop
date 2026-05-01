import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/Card";

interface KevRow {
  cveID: string;
  vendorProject?: string;
  product?: string;
  vulnerabilityName?: string;
  dateAdded?: string;
  shortDescription?: string;
}

const SQL = `
  SELECT cveID, vendorProject, product, vulnerabilityName, dateAdded, shortDescription
  FROM disa_workshop.threat_intel.kev_catalog
  ORDER BY dateAdded DESC
  LIMIT 50
`;

export default function Threats() {
  const [rows, setRows] = useState<KevRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [params] = useSearchParams();
  const cveFilter = params.get("cveId")?.toLowerCase();
  const vendorFilter = params.get("vendor")?.toLowerCase();

  useEffect(() => {
    fetch("/api/sql", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sql: SQL }),
    })
      .then((r) => r.json())
      .then((d) => (d.error ? setError(d.error) : setRows(d.rows)))
      .catch((e) => setError(String(e)));
  }, []);

  const filtered = rows.filter(
    (r) =>
      (!cveFilter || r.cveID.toLowerCase().includes(cveFilter)) &&
      (!vendorFilter || (r.vendorProject || "").toLowerCase().includes(vendorFilter))
  );

  return (
    <Card>
      <CardHeader>
        <CardTitle>KEV Catalog (recent 50)</CardTitle>
        <CardDescription>
          {filtered.length} entries{cveFilter && ` filtered by CVE "${cveFilter}"`}{vendorFilter && ` filtered by vendor "${vendorFilter}"`}
        </CardDescription>
      </CardHeader>
      <CardContent>
        {error && <div className="text-red-500 text-sm">{error}</div>}
        <div className="overflow-auto max-h-[70vh]">
          <table className="w-full text-xs">
            <thead className="text-left text-slate-400 border-b border-slate-800">
              <tr>
                <th className="py-2">CVE</th>
                <th>Vendor</th>
                <th>Product</th>
                <th>Date Added</th>
                <th>Description</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((r) => (
                <tr key={r.cveID} className="border-b border-slate-900 hover:bg-slate-900">
                  <td className="py-2 font-mono">{r.cveID}</td>
                  <td>{r.vendorProject}</td>
                  <td>{r.product}</td>
                  <td>{r.dateAdded?.slice(0, 10)}</td>
                  <td className="text-slate-400 max-w-md truncate">{r.shortDescription}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}
