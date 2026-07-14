"use server";

import { revalidatePath } from "next/cache";

const MCP_SERVER = process.env.NEXT_PUBLIC_MCP_SERVER_URL || process.env.MCP_SERVER_URL || "http://localhost:8000";

export async function getRecipientsData() {
  try {
    const res = await fetch(`${MCP_SERVER}/api/recipients`, {
      method: "GET",
      cache: "no-store",
    });
    
    if (!res.ok) {
      throw new Error("Failed to fetch recipients data");
    }
    
    return await res.json();
  } catch (error) {
    console.error("Error fetching recipients data:", error);
    return {
      recipients: [],
      preferences: {
        daily_report: true,
        critical_alerts: true,
        warning_alerts: false
      }
    };
  }
}

export async function addRecipient(email: string, label: string = "") {
  try {
    const res = await fetch(`${MCP_SERVER}/api/recipients`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ email, label }),
    });
    
    const data = await res.json();
    
    if (!res.ok) {
      return { success: false, error: data.error || "Failed to add recipient" };
    }
    
    revalidatePath("/settings");
    return { success: true, data };
  } catch (error: any) {
    return { success: false, error: error.message || "Failed to add recipient" };
  }
}

export async function removeRecipient(id: string) {
  try {
    const res = await fetch(`${MCP_SERVER}/api/recipients/${id}`, {
      method: "DELETE",
    });
    
    const data = await res.json();
    
    if (!res.ok) {
      return { success: false, error: data.error || "Failed to remove recipient" };
    }
    
    revalidatePath("/settings");
    return { success: true };
  } catch (error: any) {
    return { success: false, error: error.message || "Failed to remove recipient" };
  }
}

export async function updatePreferences(preferences: Record<string, boolean>) {
  try {
    const res = await fetch(`${MCP_SERVER}/api/recipients`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ preferences }),
    });
    
    const data = await res.json();
    
    if (!res.ok) {
      return { success: false, error: data.error || "Failed to update preferences" };
    }
    
    revalidatePath("/settings");
    return { success: true, preferences: data.preferences };
  } catch (error: any) {
    return { success: false, error: error.message || "Failed to update preferences" };
  }
}
