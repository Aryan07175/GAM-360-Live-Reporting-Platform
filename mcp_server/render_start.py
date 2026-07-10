"""
Render Startup Script — writes credential files from environment variables
before starting the MCP server.

On Render, secrets are stored as env vars. This script reconstructs the
config/googleads.yaml and config/service_account.json files at boot time
so the existing GAMClient code works unchanged.
"""

import os
import sys
import json

def setup_credentials():
    """Create credential files from environment variables for cloud deployment."""
    config_dir = os.path.join(os.path.dirname(__file__), "..", "config")
    os.makedirs(config_dir, exist_ok=True)

    # 1. Write service_account.json from env var
    sa_json = os.environ.get("GAM_SERVICE_ACCOUNT_JSON", "")
    sa_path = os.path.join(config_dir, "service_account.json")

    if sa_json:
        with open(sa_path, "w") as f:
            # Validate it's proper JSON
            parsed = json.loads(sa_json)
            json.dump(parsed, f, indent=2)
        print(f"[render_start] Wrote service_account.json ({len(sa_json)} chars)")
    else:
        if not os.path.exists(sa_path):
            print("[render_start] WARNING: GAM_SERVICE_ACCOUNT_JSON not set and no local file found!")
            print("[render_start] The server will start but GAM API calls will fail.")

    # 2. Write googleads.yaml from env vars
    network_code = os.environ.get("GAM_NETWORK_CODE", "")
    app_name = os.environ.get("GAM_APPLICATION_NAME", "GAM360-Revenue-Pipeline")
    yaml_path = os.path.join(config_dir, "googleads.yaml")
    abs_sa_path = os.path.abspath(sa_path)

    if network_code:
        yaml_content = f"""ad_manager:
 network_code: {network_code}
 application_name: {app_name}
 path_to_private_key_file: {abs_sa_path}
"""
        with open(yaml_path, "w") as f:
            f.write(yaml_content)
        print(f"[render_start] Wrote googleads.yaml (network: {network_code})")
    else:
        if not os.path.exists(yaml_path):
            print("[render_start] WARNING: GAM_NETWORK_CODE not set and no local googleads.yaml found!")

    # 3. Set the credentials path env var
    os.environ.setdefault("GAM_CREDENTIALS_PATH", os.path.abspath(yaml_path))
    print(f"[render_start] GAM_CREDENTIALS_PATH = {os.environ['GAM_CREDENTIALS_PATH']}")


if __name__ == "__main__":
    setup_credentials()

    # Now start the actual server
    print("[render_start] Starting MCP server...")
    
    # Add project root to path
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(
        "mcp_server.server:starlette_app",
        host="0.0.0.0",
        port=port,
        log_level="info",
    )
