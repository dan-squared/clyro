import os
import time
import subprocess
import tempfile
import logging

def _parse_version(v: str) -> tuple:
    return tuple(int(x) for x in v.replace('v', '').split('.') if x.isdigit())

logger = logging.getLogger(__name__)

class AutoUpdater:
    def __init__(self, current_version: str, repo_owner: str = "dan-squared", repo_name: str = "clyro"):
        """Initialize the Updater.
        Args:
            current_version: The current semantic version without 'v' prefix (e.g. '0.1.0')
        """
        self.current_version = current_version
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.api_url = f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}/releases/latest"
        
    async def check_for_updates(self) -> dict | None:
        """Check GitHub API for a newer release."""
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(self.api_url) as response:
                    if response.status == 200:
                        data = await response.json()
                        latest_tag = data.get("tag_name", "").lstrip("v")
                        
                        try:
                            if _parse_version(latest_tag) > _parse_version(self.current_version):
                                logger.info(f"New update found: {latest_tag}")
                                
                                # Find the Windows installer asset
                                installer_asset = None
                                for asset in data.get("assets", []):
                                    if asset.get("name") == "ClyroSetup.exe":
                                        installer_asset = asset
                                        break
                                
                                if installer_asset:
                                    return {
                                        "version": latest_tag,
                                        "download_url": installer_asset.get("browser_download_url"),
                                        "notes": data.get("body", "")
                                    }
                        except ValueError:
                            logger.error(f"Cannot parse version tag: {latest_tag}")
        except Exception as e:
            logger.error(f"Failed to check for updates: {e}")
            
        return None

    async def download_and_install(self, download_url: str):
        """Download the installer and run it."""
        try:
            import aiohttp
            temp_dir = tempfile.gettempdir()
            installer_path = os.path.join(temp_dir, f"ClyroSetup_update_{int(time.time())}.exe")
            
            # Download file
            logger.info(f"Downloading update from {download_url}")
            async with aiohttp.ClientSession() as session:
                async with session.get(download_url) as response:
                    if response.status == 200:
                        with open(installer_path, 'wb') as f:
                            while True:
                                chunk = await response.content.read(1024 * 1024)
                                if not chunk:
                                    break
                                f.write(chunk)
                                
            # Execute installer
            logger.info("Executing installer...")
            # Use /SILENT or /VERYSILENT for Inno Setup to run without prompts
            subprocess.Popen([installer_path, "/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART"])
            
            # Application needs to yield control to let installer over-write files
            from PyQt6.QtWidgets import QApplication
            from PyQt6.QtCore import QMetaObject, Qt
            app = QApplication.instance()
            if app:
                QMetaObject.invokeMethod(app, "quit", Qt.ConnectionType.QueuedConnection)
            
        except Exception as e:
            logger.error(f"Failed to download and install update: {e}")
