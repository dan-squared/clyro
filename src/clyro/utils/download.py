import urllib.request
import urllib.parse
from pathlib import Path
from PyQt6.QtCore import QThread, pyqtSignal

class DownloadWorker(QThread):
    progress_updated = pyqtSignal(int, str)  # percentage, detail
    download_completed = pyqtSignal(Path, str)  # temp_path, original_url
    download_failed = pyqtSignal(str, str)  # error_message, original_url

    def __init__(self, url: str, temp_dir: Path):
        super().__init__()
        self.url = url
        self.temp_dir = temp_dir
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        try:
            # Create a safe temporary filename from the URL, ignoring queries/fragments
            parsed = urllib.parse.urlparse(self.url)
            # unquote the url to remove %20, etc
            path = urllib.parse.unquote(parsed.path)
            filename = Path(path).name
            
            # Sometimes paths end with slashes or are empty, fallback to generated
            if not filename or filename == "/":
                filename = "downloaded_file.bin"
                
            # Strip off any remaining query-like weirdness that sneaks into the path part
            # e.g some CDNs use `/image.png@avif` or `/image.jpg?width=500`
            if "@" in filename:
                filename = filename.split("@")[0]
            if "?" in filename:
                filename = filename.split("?")[0]
                
            ext = Path(filename).suffix.lower()
            if not ext:
                # Best guess if we can't find one. Opt for jpg if image guessed from headers later, but default to bin
                filename += ".jpeg"
            # For simplicity, just make sure there's a unique temp path
            import uuid
            clean_filename = f"{uuid.uuid4().hex[:8]}_{filename}"
            
            # Ensure the filename is within bounds
            if len(clean_filename) > 200:
                clean_filename = clean_filename[-200:]
                
            temp_path = self.temp_dir / clean_filename
            self.temp_dir.mkdir(parents=True, exist_ok=True)

            req = urllib.request.Request(self.url, headers={'User-Agent': 'Mozilla/5.0'})
            
            with urllib.request.urlopen(req, timeout=30) as response:
                total_size = response.getheader('Content-Length')
                total_size = int(total_size) if total_size else 0
                
                # Guard against excessively large downloads (500MB limit)
                max_size = 500 * 1024 * 1024  # 500 MB
                if total_size > max_size:
                    self.download_failed.emit(
                        f"File too large ({total_size / (1024*1024):.0f} MB, max {max_size // (1024*1024)} MB)",
                        self.url
                    )
                    return
                
                downloaded = 0
                chunk_size = 1024 * 64  # 64 KB

                with open(temp_path, 'wb') as f:
                    while True:
                        if self._is_cancelled:
                            temp_path.unlink(missing_ok=True)
                            self.download_failed.emit("Cancelled", self.url)
                            return

                        chunk = response.read(chunk_size)
                        if not chunk:
                            break
                            
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        if total_size > 0:
                            pct = int((downloaded / total_size) * 100)
                            self.progress_updated.emit(pct, "Downloading...")
                        else:
                            # Indeterminate progress
                            mb = downloaded / (1024 * 1024)
                            self.progress_updated.emit(0, f"Downloading... {mb:.1f}MB")

            self.download_completed.emit(temp_path, self.url)

        except Exception as e:
            self.download_failed.emit(str(e), self.url)
