"use client";

import { BIReportData } from "@/types";
import { Button } from "@/components/ui/button";
import { Download, FileText, FileSpreadsheet, Printer } from "lucide-react";

interface Props {
  data: BIReportData;
}

export function ReportExportBar({ data }: Props) {
  const handleCSV = () => {
    const headers = ["Rank", "Application", "Revenue (USD)", "Impressions", "Clicks", "CTR %", "eCPM", "Fill Rate %", "Ad Requests", "Revenue %"];
    const rows = data.apps.map((a) =>
      [a.rank, a.ad_unit_name, a.revenue_usd.toFixed(6), a.impressions, a.clicks, a.ctr_pct.toFixed(2), a.ecpm_usd.toFixed(6), a.fill_rate_pct.toFixed(1), a.ad_requests, a.revenue_pct.toFixed(2)].join(",")
    );
    const csv = [headers.join(","), ...rows].join("\n");
    downloadFile(csv, `bi-report-${data.startDate}-to-${data.endDate}.csv`, "text/csv");
  };

  const handleMarkdown = () => {
    let md = `# Executive BI Report\n\n**Period:** ${data.startDate} to ${data.endDate}\n\n`;

    md += `## Executive Summary\n\n`;
    md += `| Metric | Value | Change |\n|--------|-------|--------|\n`;
    data.summary.forEach((k) => {
      md += `| ${k.label} | ${k.formatted} | ${k.direction === "up" ? "↑" : k.direction === "down" ? "↓" : "–"} ${k.changePct.toFixed(1)}% |\n`;
    });

    md += `\n## Application Performance\n\n`;
    md += `| Rank | Application | Revenue | Impressions | eCPM | Fill Rate | Contribution |\n`;
    md += `|------|-------------|---------|-------------|------|-----------|-------------|\n`;
    data.apps.forEach((a) => {
      md += `| ${a.rank} | ${a.ad_unit_name} | $${a.revenue_usd.toFixed(6)} | ${a.impressions.toLocaleString()} | $${a.ecpm_usd.toFixed(6)} | ${a.fill_rate_pct.toFixed(1)}% | ${a.revenue_pct.toFixed(1)}% |\n`;
    });

    if (data.anomalies.length > 0) {
      md += `\n## Anomalies\n\n`;
      data.anomalies.forEach((a) => {
        md += `- **[${a.severity}]** ${a.description}\n`;
      });
    }

    if (data.insights.length > 0) {
      md += `\n## AI Insights\n\n`;
      data.insights.forEach((i) => {
        md += `### ${i.icon} ${i.title}\n${i.description}\n\n`;
      });
    }

    downloadFile(md, `bi-report-${data.startDate}-to-${data.endDate}.md`, "text/markdown");
  };

  const handleExcel = () => {
    // Export as CSV with .xlsx-compatible format (tab-separated)
    const headers = ["Rank", "Application", "Revenue (USD)", "Impressions", "Clicks", "CTR %", "eCPM", "Fill Rate %", "Ad Requests", "Revenue %"];
    const rows = data.apps.map((a) =>
      [a.rank, a.ad_unit_name, a.revenue_usd, a.impressions, a.clicks, a.ctr_pct, a.ecpm_usd, a.fill_rate_pct, a.ad_requests, a.revenue_pct].join("\t")
    );
    const tsv = [headers.join("\t"), ...rows].join("\n");
    downloadFile(tsv, `bi-report-${data.startDate}-to-${data.endDate}.xls`, "application/vnd.ms-excel");
  };

  const handlePDF = () => {
    window.print();
  };

  return (
    <div className="flex items-center gap-2 flex-wrap">
      <Button variant="outline" size="sm" onClick={handleCSV} className="gap-1.5 text-xs">
        <Download className="h-3.5 w-3.5" /> CSV
      </Button>
      <Button variant="outline" size="sm" onClick={handleMarkdown} className="gap-1.5 text-xs">
        <FileText className="h-3.5 w-3.5" /> Markdown
      </Button>
      <Button variant="outline" size="sm" onClick={handleExcel} className="gap-1.5 text-xs">
        <FileSpreadsheet className="h-3.5 w-3.5" /> Excel
      </Button>
      <Button variant="outline" size="sm" onClick={handlePDF} className="gap-1.5 text-xs">
        <Printer className="h-3.5 w-3.5" /> PDF
      </Button>
    </div>
  );
}

function downloadFile(content: string, filename: string, mimeType: string) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
