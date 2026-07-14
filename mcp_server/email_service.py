import os
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formatdate
import logging
from typing import List, Dict, Any

log = logging.getLogger("email_service")


def _get_credentials():
    """
    Load and sanitise Gmail credentials from environment.
    Gmail App Passwords are displayed as 'xxxx xxxx xxxx xxxx' — if copy-pasted
    with spaces they will silently fail SMTP login. Strip all whitespace.
    """
    sender_email = (os.getenv("GMAIL_SENDER_EMAIL") or "").strip()
    app_password = (os.getenv("GMAIL_APP_PASSWORD") or "").replace(" ", "").strip()
    return sender_email or None, app_password or None


def log_credential_status():
    """
    Called once at server startup. Logs whether credentials are present
    WITHOUT printing their actual values.
    """
    sender_email, app_password = _get_credentials()
    log.info(
        "[EMAIL_CREDENTIALS] GMAIL_SENDER_EMAIL present=%s | "
        "GMAIL_APP_PASSWORD present=%s | "
        "password_len=%s",
        bool(sender_email),
        bool(app_password),
        len(app_password) if app_password else 0,
    )
    if app_password and len(app_password) not in (16,):
        log.warning(
            "[EMAIL_CREDENTIALS] GMAIL_APP_PASSWORD length is %d — expected 16 "
            "(without spaces). Verify you copied the correct App Password.",
            len(app_password),
        )


def _send_email(subject: str, html_content: str, to_emails: List[str], pdf_bytes: bytes = None, pdf_filename: str = None) -> Dict[str, Any]:
    if not to_emails:
        log.info("[EMAIL_SKIPPED] No recipients provided. Skipping email send.")
        return {"error": "No recipients", "status": "skipped"}

    sender_email, app_password = _get_credentials()
    if not sender_email or not app_password:
        msg = (
            "GMAIL_SENDER_EMAIL missing." if not sender_email else ""
            + " GMAIL_APP_PASSWORD missing." if not app_password else ""
        ).strip()
        log.error("[EMAIL_SEND_FAILED] Gmail credentials not configured: %s", msg)
        return {"error": f"Credentials missing: {msg}", "status": "error"}

    msg_obj = EmailMessage()
    msg_obj['Subject'] = subject
    msg_obj['From'] = f"GAM 360 Live <{sender_email}>"
    msg_obj['To'] = ", ".join(to_emails)
    msg_obj['Date'] = formatdate(localtime=True)

    msg_obj.set_content("Please enable HTML to view this email.")
    msg_obj.add_alternative(html_content, subtype='html')
    
    if pdf_bytes and pdf_filename:
        msg_obj.add_attachment(pdf_bytes, maintype='application', subtype='pdf', filename=pdf_filename)

    try:
        context = ssl.create_default_context()
        log.info(
            "[EMAIL_SEND] Attempting SMTP_SSL to smtp.gmail.com:465 → %d recipient(s) | subject=%r",
            len(to_emails), subject,
        )
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context, timeout=30) as server:
            server.login(sender_email, app_password)
            server.send_message(msg_obj)

        log.info("[EMAIL_SENT] Successfully sent %r to %s", subject, to_emails)
        return {"status": "success", "recipients": to_emails}

    except smtplib.SMTPAuthenticationError as e:
        log.error(
            "[EMAIL_SEND_FAILED] SMTP authentication failed. "
            "Verify GMAIL_SENDER_EMAIL and GMAIL_APP_PASSWORD are correct, "
            "and that 2-Step Verification is enabled on the Gmail account. "
            "Error: %s", e,
        )
        return {"error": f"Authentication failed: {e}", "status": "error"}
    except smtplib.SMTPConnectError as e:
        log.error("[EMAIL_SEND_FAILED] SMTP connection error (port/network issue): %s", e)
        return {"error": f"Connection error: {e}", "status": "error"}
    except smtplib.SMTPRecipientsRefused as e:
        log.error("[EMAIL_SEND_FAILED] SMTP recipients refused: %s", e)
        return {"error": f"Recipients refused: {e}", "status": "error"}
    except TimeoutError as e:
        log.error("[EMAIL_SEND_FAILED] SMTP connection timed out: %s", e)
        return {"error": f"Timeout: {e}", "status": "error"}
    except Exception as e:
        log.error("[EMAIL_SEND_FAILED] Unexpected error sending email: %s", e, exc_info=True)
        return {"error": str(e), "status": "error"}


def send_test_email(to_email: str) -> Dict[str, Any]:
    """Send a minimal diagnostic test email to verify SMTP config end-to-end."""
    html = """
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                max-width: 500px; margin: 0 auto; padding: 30px;
                background: #0f172a; color: #f1f5f9; border-radius: 12px;">
        <h2 style="color: #6366f1; margin-top: 0;">✅ GAM 360 Test Email</h2>
        <p>This is a diagnostic test email sent from your GAM 360 Live Reporting Platform.</p>
        <p>If you're reading this, Gmail SMTP is working correctly! 🎉</p>
        <hr style="border-color: #334155; margin: 20px 0;">
        <p style="color: #94a3b8; font-size: 13px;">
            Sent via Render backend → smtp.gmail.com:465 (SMTP_SSL)
        </p>
    </div>
    """
    return _send_email("🔔 GAM 360 — Test Email", html, [to_email])


def send_alert_email(alert: Dict[str, Any], to_emails: List[str], prefs: Dict[str, bool] = None) -> Dict[str, Any]:
    if not to_emails:
        return {"error": "No recipients", "status": "skipped"}

    severity = alert.get("severity", "warning").lower()
    title = alert.get("title", "Unknown Alert")
    metric = alert.get("metric", "Unknown Metric")
    value = alert.get("value", "")

    # Log which toggle was checked
    if prefs is not None:
        if severity == "critical" and not prefs.get("critical_alerts", True):
            log.info("[EMAIL_SKIPPED] Critical alert emails toggle is OFF — skipping: %s", title)
            return {"status": "skipped", "reason": "critical_alerts toggle is OFF"}
        if severity == "warning" and not prefs.get("warning_alerts", False):
            log.info("[EMAIL_SKIPPED] Warning alert emails toggle is OFF — skipping: %s", title)
            return {"status": "skipped", "reason": "warning_alerts toggle is OFF"}

    log.info("[EMAIL_ALERT] Sending %s alert email: %s", severity.upper(), title)

    prefix = "🔴 CRITICAL:" if severity == "critical" else "🟠 WARNING:"
    subject = f"{prefix} {title}"

    color = "#ef4444" if severity == "critical" else "#f59e0b"
    bg_color = "#fef2f2" if severity == "critical" else "#fffbeb"

    html = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e5e7eb; border-radius: 8px; background-color: #ffffff;">
        <h2 style="color: {color}; margin-top: 0; display: flex; align-items: center;">
            <span style="background-color: {bg_color}; padding: 8px 12px; border-radius: 6px; font-size: 18px;">
                {prefix} GAM 360 Live Alert
            </span>
        </h2>
        
        <div style="padding: 20px 0; border-top: 1px solid #e5e7eb; border-bottom: 1px solid #e5e7eb; margin: 20px 0;">
            <h3 style="margin: 0 0 10px 0; color: #111827; font-size: 20px;">{title}</h3>
            
            <table style="width: 100%; border-collapse: collapse; margin-top: 15px;">
                <tr>
                    <td style="padding: 8px 0; color: #6b7280; width: 100px;">Metric:</td>
                    <td style="padding: 8px 0; color: #111827; font-weight: 600;">{metric}</td>
                </tr>
                <tr>
                    <td style="padding: 8px 0; color: #6b7280;">Value:</td>
                    <td style="padding: 8px 0; color: #111827; font-weight: 600;">{value}</td>
                </tr>
                <tr>
                    <td style="padding: 8px 0; color: #6b7280;">Severity:</td>
                    <td style="padding: 8px 0; color: {color}; font-weight: 600; text-transform: capitalize;">{severity}</td>
                </tr>
            </table>
        </div>
        
        <p style="color: #6b7280; font-size: 13px; margin: 0;">
            This is an automated alert generated by the GAM 360 Live Reporting Engine based on real-time data.
        </p>
    </div>
    """

    return _send_email(subject, html, to_emails)


def send_daily_report_email(report_data: Dict[str, Any], to_emails: List[str]) -> Dict[str, Any]:
    if not to_emails:
        return {"error": "No recipients", "status": "skipped"}

    summary = report_data.get("executive_summary", {})
    period = summary.get("period", "Unknown Period")

    subject = f"📊 GAM 360 Live Executive Report: {period}"

    # Extract metrics safely
    rev = summary.get('total_revenue_usd', 0)
    imp = summary.get('total_impressions', 0)
    ecpm = summary.get('average_ecpm', 0)
    ctr = summary.get('average_ctr', 0)
    fill = summary.get('average_fill_rate', 0)

    # Top apps table
    apps = report_data.get("top_apps", [])
    apps_rows = ""
    for idx, app in enumerate(apps):
        a_name = app.get("ad_unit_name", "")
        a_rev = app.get("ad_server_cpm_and_cpc_revenue", 0)
        a_imp = app.get("ad_server_impressions", 0)
        apps_rows += f"""
        <tr>
            <td style="padding: 10px; border-bottom: 1px solid #374151; color: #f3f4f6;">{idx+1}. {a_name}</td>
            <td style="padding: 10px; border-bottom: 1px solid #374151; text-align: right; color: #f3f4f6;">${a_rev:,.2f}</td>
            <td style="padding: 10px; border-bottom: 1px solid #374151; text-align: right; color: #9ca3af;">{a_imp:,}</td>
        </tr>
        """

    # Anomalies
    anomalies = report_data.get("anomalies", [])
    anomalies_html = ""
    if anomalies:
        anomalies_rows = ""
        for a in anomalies:
            desc = a.get("description", "")
            sev = a.get("severity", "")
            color = "#ef4444" if sev == "High" else "#f59e0b" if sev == "Medium" else "#3b82f6"
            anomalies_rows += f"""
            <div style="margin-bottom: 8px; padding-left: 12px; border-left: 3px solid {color}; color: #d1d5db;">
                {desc}
            </div>
            """
        anomalies_html = f"""
        <div style="margin-top: 30px; background-color: #1f2937; padding: 20px; border-radius: 8px;">
            <h3 style="margin-top: 0; color: #f3f4f6; font-size: 18px;">⚠️ Detected Anomalies</h3>
            {anomalies_rows}
        </div>
        """

    # Recommendations
    recs = report_data.get("recommendations", [])
    recs_html = ""
    if recs:
        recs_rows = ""
        for r in recs:
            title = r.get("title", "")
            desc = r.get("description", "")
            recs_rows += f"""
            <div style="margin-bottom: 12px; color: #d1d5db;">
                <strong style="color: #60a5fa;">• {title}:</strong> {desc}
            </div>
            """
        recs_html = f"""
        <div style="margin-top: 20px; background-color: #1f2937; padding: 20px; border-radius: 8px;">
            <h3 style="margin-top: 0; color: #f3f4f6; font-size: 18px;">💡 Recommendations</h3>
            {recs_rows}
        </div>
        """

    html = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; max-width: 650px; margin: 0 auto; background-color: #111827; color: #f3f4f6; padding: 30px; border-radius: 12px;">
        
        <div style="text-align: center; margin-bottom: 30px;">
            <h1 style="color: #ffffff; margin-bottom: 5px; font-size: 24px;">GAM 360 Live Executive Report</h1>
            <p style="color: #9ca3af; margin-top: 0;">Period: {period}</p>
        </div>
        
        <div style="background-color: #1f2937; padding: 20px; border-radius: 8px; margin-bottom: 20px;">
            <h3 style="margin-top: 0; color: #f3f4f6; font-size: 18px; border-bottom: 1px solid #374151; padding-bottom: 10px;">Executive Summary</h3>
            <div style="display: flex; flex-wrap: wrap; margin-top: 15px;">
                <div style="flex: 1; min-width: 120px; margin-bottom: 15px;">
                    <div style="color: #9ca3af; font-size: 12px; text-transform: uppercase;">Total Revenue</div>
                    <div style="color: #10b981; font-size: 24px; font-weight: 600;">${rev:,.2f}</div>
                </div>
                <div style="flex: 1; min-width: 120px; margin-bottom: 15px;">
                    <div style="color: #9ca3af; font-size: 12px; text-transform: uppercase;">Impressions</div>
                    <div style="color: #f3f4f6; font-size: 24px; font-weight: 600;">{imp:,}</div>
                </div>
                <div style="flex: 1; min-width: 120px; margin-bottom: 15px;">
                    <div style="color: #9ca3af; font-size: 12px; text-transform: uppercase;">Avg eCPM</div>
                    <div style="color: #f3f4f6; font-size: 24px; font-weight: 600;">${ecpm:,.2f}</div>
                </div>
            </div>
            <div style="display: flex; flex-wrap: wrap;">
                <div style="flex: 1; min-width: 120px;">
                    <div style="color: #9ca3af; font-size: 12px; text-transform: uppercase;">Fill Rate</div>
                    <div style="color: #f3f4f6; font-size: 18px;">{fill:,.1f}%</div>
                </div>
                <div style="flex: 1; min-width: 120px;">
                    <div style="color: #9ca3af; font-size: 12px; text-transform: uppercase;">CTR</div>
                    <div style="color: #f3f4f6; font-size: 18px;">{ctr:,.2f}%</div>
                </div>
                <div style="flex: 1; min-width: 120px;"></div>
            </div>
        </div>

        <div style="background-color: #1f2937; padding: 20px; border-radius: 8px;">
            <h3 style="margin-top: 0; color: #f3f4f6; font-size: 18px; border-bottom: 1px solid #374151; padding-bottom: 10px;">Top Performing Applications</h3>
            <table style="width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 14px;">
                <thead>
                    <tr>
                        <th style="text-align: left; padding: 10px; color: #9ca3af; border-bottom: 1px solid #374151;">Application</th>
                        <th style="text-align: right; padding: 10px; color: #9ca3af; border-bottom: 1px solid #374151;">Revenue</th>
                        <th style="text-align: right; padding: 10px; color: #9ca3af; border-bottom: 1px solid #374151;">Impressions</th>
                    </tr>
                </thead>
                <tbody>
                    {apps_rows}
                </tbody>
            </table>
        </div>
        
        {anomalies_html}
        
        {recs_html}

        <div style="margin-top: 40px; text-align: center; color: #6b7280; font-size: 12px;">
            <p>Generated automatically by GAM 360 Live Reporting Platform.</p>
            <p>You received this because you are subscribed to Daily Reports.</p>
        </div>
    </div>
    """

    pdf_bytes = None
    try:
        from xhtml2pdf import pisa
        import io
        
        # xhtml2pdf handles basic HTML but does better with a full document structure
        pdf_html = f"<html><head><meta charset='utf-8'></head><body style='background-color: #ffffff;'>{html.replace('color: #f3f4f6;', 'color: #333333;').replace('color: #ffffff;', 'color: #111111;').replace('background-color: #111827;', 'background-color: #ffffff;').replace('background-color: #1f2937;', 'background-color: #f9fafb;')}</body></html>"
        
        pdf_buf = io.BytesIO()
        pisa_status = pisa.CreatePDF(pdf_html, dest=pdf_buf)
        if not pisa_status.err:
            pdf_bytes = pdf_buf.getvalue()
    except Exception as e:
        log.error(f"[EMAIL_PDF_ERROR] Failed to generate PDF: {e}")

    return _send_email(subject, html, to_emails, pdf_bytes=pdf_bytes, pdf_filename=f"GAM_360_Report_{period}.pdf")
