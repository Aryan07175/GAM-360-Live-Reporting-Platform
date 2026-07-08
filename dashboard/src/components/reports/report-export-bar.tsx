"use client";

import type { LiveReportData } from "@/types";
import { Button } from "@/components/ui/button";
import { Download, FileText, FileSpreadsheet, Printer } from "lucide-react";
import { exportToCSV, exportToExcel, exportToMarkdown, exportToPDF } from "@/services/export-service";

interface Props {
  data: LiveReportData;
}

export function ReportExportBar({ data }: Props) {
  return (
    <div className="flex items-center gap-2 flex-wrap">
      <Button variant="outline" size="sm" onClick={() => exportToCSV(data)} className="gap-1.5 text-xs">
        <Download className="h-3.5 w-3.5" /> CSV
      </Button>
      <Button variant="outline" size="sm" onClick={() => exportToMarkdown(data)} className="gap-1.5 text-xs">
        <FileText className="h-3.5 w-3.5" /> Markdown
      </Button>
      <Button variant="outline" size="sm" onClick={() => exportToExcel(data)} className="gap-1.5 text-xs">
        <FileSpreadsheet className="h-3.5 w-3.5" /> Excel
      </Button>
      <Button variant="outline" size="sm" onClick={() => exportToPDF()} className="gap-1.5 text-xs">
        <Printer className="h-3.5 w-3.5" /> PDF
      </Button>
    </div>
  );
}
