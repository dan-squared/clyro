IPC_HOST = "127.0.0.1"
IPC_PORT = 19847


def build_ipc_url(endpoint: str) -> str:
    endpoint = endpoint.lstrip("/")
    return f"http://{IPC_HOST}:{IPC_PORT}/{endpoint}"
