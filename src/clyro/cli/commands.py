import typer
import requests
from typing import List
from pathlib import Path

app = typer.Typer(help="Clyro CLI. Dispatches commands to the running Clyro process via IPC.")

def _dispatch(endpoint: str, paths: List[Path], **kwargs):
    try:
        url = f"http://localhost:12345/{endpoint}"
        payload = {
            "paths": [str(p.absolute()) for p in paths]
        }
        payload.update(kwargs)
        
        r = requests.post(url, json=payload)
        if r.status_code == 200:
            typer.echo(f"Successfully queued {len(paths)} file(s).")
        else:
            typer.echo(f"Failed: {r.status_code} - {r.text}", err=True)
            
    except requests.exceptions.ConnectionError:
        typer.echo("Error: Could not connect to Clyro. Is the app running?", err=True)

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
