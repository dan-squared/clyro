import json
import urllib.error
import urllib.request
from typing import List
from pathlib import Path

import typer

from clyro.ipc.constants import build_ipc_url

app = typer.Typer(help="Clyro CLI. Dispatches commands to the running Clyro process via IPC.")

def _dispatch(endpoint: str, paths: List[Path], **kwargs):
    url = build_ipc_url(endpoint)
    payload = {
        "paths": [str(p.absolute()) for p in paths]
    }
    payload.update(kwargs)
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=2.0) as response:
            if response.status == 200:
                typer.echo(f"Successfully queued {len(paths)} file(s).")
                return
            body = response.read().decode("utf-8", "replace")
            typer.echo(f"Failed: {response.status} - {body}", err=True)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        typer.echo(f"Failed: {e.code} - {body}", err=True)
    except urllib.error.URLError:
        typer.echo("Error: Could not connect to Clyro. Is the app running?", err=True)
    except TimeoutError:
        typer.echo("Error: Timed out while talking to Clyro.", err=True)

@app.command()
def optimize(
    files: List[Path] = typer.Argument(..., help="Files to optimize"),
    aggressive: bool = typer.Option(False, "--aggressive", "-a", help="Use aggressive compression")
):
    """Optimize files using the current Clyro settings."""
    _dispatch("optimize", files, aggressive=aggressive)

@app.command()
def convert(
    files: List[Path] = typer.Argument(..., help="Files to convert"),
    target_format: str = typer.Option(..., "--format", "-f", help="Target format (e.g. jpg, pdf, mp4)")
):
    """Convert files to a new format using Clyro."""
    _dispatch("convert", files, target_format=target_format)

def main():
    app()

if __name__ == "__main__":
    main()
