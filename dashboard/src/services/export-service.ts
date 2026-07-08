/**
 * Export Service — Generate exports from live data
 * 
 * All exports use the live data currently displayed on screen.
 * Never fetches from storage. PDF/CSV/Excel/Markdown.
 */

import type { LiveReportData, BIAppRow, BISummaryKPI, BIAnomaly, BIInsight, Recommendation } from "@/types";

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

export function exportToCSV(data: LiveReportData) {
  const headers = [
    "Rank", "Application", "Revenue (USD)", "Impressions", "Clicks",
    "CTR %", "eCPM", "Fill Rate %", "Ad Requests", "Revenue %",
  ];
  const rows = data.apps.map((a) =>
    [
      a.rank, `"${a.ad_unit_name}"`, a.revenue_usd.toFixed(6), a.impressions,
      a.clicks, a.ctr_pct.toFixed(2), a.ecpm_usd.toFixed(6),
      a.fill_rate_pct.toFixed(1), a.ad_requests, a.revenue_pct.toFixed(2),
    ].join(",")
  );
  const csv = [headers.join(","), ...rows].join("\n");
  downloadFile(csv, `gam360-live-report-${data.startDate}-to-${data.endDate}.csv`, "text/csv");
}

export function exportToExcel(data: LiveReportData) {
  const headers = [
    "Rank", "Application", "Revenue (USD)", "Impressions", "Clicks",
    "CTR %", "eCPM", "Fill Rate %", "Ad Requests", "Revenue %",
  ];
  const rows = data.apps.map((a) =>
    [
      a.rank, a.ad_unit_name, a.revenue_usd, a.impressions,
      a.clicks, a.ctr_pct, a.ecpm_usd, a.fill_rate_pct,
      a.ad_requests, a.revenue_pct,
    ].join("\t")
  );
  const tsv = [headers.join("\t"), ...rows].join("\n");
  downloadFile(tsv, `gam360-live-report-${data.startDate}-to-${data.endDate}.xls`, "application/vnd.ms-excel");
}

export function exportToMarkdown(data: LiveReportData) {
  let md = `# GAM 360 Live Report\n\n`;
  md += `**Period:** ${data.startDate} to ${data.endDate}\n`;
  md += `**Generated:** ${new Date(data.fetchedAt).toLocaleString()}\n`;
  md += `**Source:** Live Google Ad Manager Data\n\n`;

  // Executive Summary
  md += `## Executive Summary\n\n`;
  md += `| Metric | Value |\n|--------|-------|\n`;
  data.summary.forEach((k) => {
    md += `| ${k.label} | ${k.formatted} |\n`;
  });

  // Application Performance
  md += `\n## Application Performance\n\n`;
  md += `| Rank | Application | Revenue | Impressions | eCPM | Fill Rate | CTR | Contribution |\n`;
  md += `|------|-------------|---------|-------------|------|-----------|-----|-------------|\n`;
  data.apps.forEach((a) => {
    md += `| ${a.rank} | ${a.ad_unit_name} | $${a.revenue_usd.toFixed(6)} | ${a.impressions.toLocaleString()} | $${a.ecpm_usd.toFixed(6)} | ${a.fill_rate_pct.toFixed(1)}% | ${a.ctr_pct.toFixed(2)}% | ${a.revenue_pct.toFixed(1)}% |\n`;
  });

  // Anomalies
  if (data.anomalies.length > 0) {
    md += `\n## Anomalies Detected\n\n`;
    data.anomalies.forEach((a: any) => {
      md += `- **[${a.severity}]** ${a.description}\n`;
    });
  }

  // Insights
  if (data.insights.length > 0) {
    md += `\n## Business Insights\n\n`;
    data.insights.forEach((i: any) => {
      md += `### ${i.icon} ${i.title}\n${i.description}\n\n`;
    });
  }

  // Recommendations
  if (data.recommendations.length > 0) {
    md += `\n## Recommendations\n\n`;
    data.recommendations.forEach((r: any) => {
      md += `- **[${r.priority}]** ${r.title}: ${r.description}\n`;
    });
  }

  downloadFile(md, `gam360-live-report-${data.startDate}-to-${data.endDate}.md`, "text/markdown");
}

export function exportToPDF() {
  window.print();
}
