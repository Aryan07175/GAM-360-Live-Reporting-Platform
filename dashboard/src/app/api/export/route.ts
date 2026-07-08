import { NextResponse } from "next/server";
import { fetchRevenueByApplication } from "@/actions/report-actions";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  let date = searchParams.get("date");

  // Fallback to yesterday if no date provided
  if (!date) {
    const yesterday = new Date();
    yesterday.setDate(yesterday.getDate() - 1);
    date = yesterday.toISOString().split("T")[0];
  }

  const result = await fetchRevenueByApplication(date, date);

  if (!result || !result.apps) {
    return new NextResponse("No data available", { status: 404 });
  }

  // Generate CSV content
  const header = [
    "Rank",
    "App Name",
    "Ad Unit ID",
    "Revenue (USD)",
    "Impressions",
    "Clicks",
    "Ad Requests",
    "Fill Rate (%)",
    "CTR (%)",
    "eCPM (USD)",
  ].join(",");

  const rows = result.apps.map((row) =>
    [
      row.rank,
      `"${row.ad_unit_name}"`,
      `"${row.ad_unit_id}"`,
      row.revenue_usd,
      row.impressions,
      row.clicks,
      row.ad_requests,
      row.fill_rate_pct,
      row.ctr_pct,
      row.ecpm_usd,
    ].join(",")
  );

  const csv = [header, ...rows].join("\n");

  return new NextResponse(csv, {
    headers: {
      "Content-Type": "text/csv",
      "Content-Disposition": `attachment; filename="gam_live_report_${date}.csv"`,
    },
  });
}
