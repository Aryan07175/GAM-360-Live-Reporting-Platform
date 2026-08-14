import mcp_server.server as server_module

try:
    print("Testing build_chat_system_prompt")
    prompt = server_module.build_chat_system_prompt({"_live_data_status": "unavailable"})
    print("Length of prompt:", len(prompt))
except Exception as e:
    import traceback
    traceback.print_exc()
