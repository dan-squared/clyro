import hashlib
import logging
import os
import re
import subprocess
import tempfile
import time

def _parse_version(v: str) -> tuple:
    return tuple(int(x) for x in v.replace('v', '').split('.') if x.isdigit())


def _normalize_sha256(value: str | None) -> str | None:
    if not value:
        return None

    match = re.search(r"([a-fA-F0-9]{64})", value)
    if not match:
        return None
    return match.group(1).lower()


def _parse_checksum_text(text: str, installer_name: str) -> str | None:
    pattern = re.compile(
        rf"([a-fA-F0-9]{{64}})\s+[* ]?{re.escape(installer_name)}(?:\s|$)",
        re.IGNORECASE,
    )
    for line in text.splitlines():
        match = pattern.search(line.strip())
        if match:
            return match.group(1).lower()
    return None


def _body_checksum_for_installer(body: str, installer_name: str) -> str | None:
    if not body:
        return None

    named = re.search(
        rf"{re.escape(installer_name)}.{{0,80}}?([a-fA-F0-9]{{64}})",
        body,
        re.IGNORECASE | re.DOTALL,
    )
    if named:
        return named.group(1).lower()
    return None


def _sha256_for_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

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

    @staticmethod
    def _find_installer_asset(assets: list[dict]) -> dict | None:
        for asset in assets:
            name = asset.get("name", "")
            if name.lower().startswith("clyrosetup") and name.lower().endswith(".exe"):
                return asset
        return None

    @staticmethod
    def _find_checksum_asset(assets: list[dict]) -> dict | None:
        candidates = {
            "checksums.txt",
            "checksums.sha256",
            "sha256sums.txt",
            "sha256sum.txt",
            "sha256.txt",
        }
        for asset in assets:
            name = asset.get("name", "").lower()
            if name in candidates:
                return asset
        return None

    async def _published_checksum(self, session, release_data: dict, installer_asset: dict) -> tuple[str | None, str | None]:
        digest = _normalize_sha256(installer_asset.get("digest"))
        if digest:
            return digest, "release asset digest"

        installer_name = installer_asset.get("name", "")
        body_checksum = _body_checksum_for_installer(release_data.get("body", ""), installer_name)
        if body_checksum:
            return body_checksum, "release notes"

        checksum_asset = self._find_checksum_asset(release_data.get("assets", []))
        if not checksum_asset:
            return None, None

        checksum_url = checksum_asset.get("browser_download_url")
        if not checksum_url:
            return None, None

        async with session.get(checksum_url) as response:
            if response.status != 200:
                return None, None
            checksum_text = await response.text()

        checksum = _parse_checksum_text(checksum_text, installer_name)
        if checksum:
            return checksum, checksum_asset.get("name") or "checksum file"
        return None, None
        
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
                                installer_asset = self._find_installer_asset(data.get("assets", []))
                                
                                if installer_asset:
                                    checksum, checksum_source = await self._published_checksum(session, data, installer_asset)
                                    return {
                                        "version": latest_tag,
                                        "installer_name": installer_asset.get("name"),
                                        "download_url": installer_asset.get("browser_download_url"),
                                        "release_url": data.get("html_url", ""),
                                        "notes": data.get("body", ""),
                                        "sha256": checksum,
                                        "checksum_source": checksum_source,
                                    }
                        except ValueError:
                            logger.error(f"Cannot parse version tag: {latest_tag}")
        except Exception as e:
            logger.error(f"Failed to check for updates: {e}")
            
        return None

    async def download_installer(self, download_url: str, expected_sha256: str | None = None) -> str:
        """Download the installer and return the local path."""
        try:
            import aiohttp

            temp_dir = tempfile.gettempdir()
            installer_path = os.path.join(temp_dir, f"ClyroSetup_update_{int(time.time())}.exe")

            logger.info(f"Downloading update from {download_url}")
            async with aiohttp.ClientSession() as session:
                async with session.get(download_url) as response:
                    if response.status != 200:
                        raise RuntimeError(f"Update download failed with HTTP {response.status}.")
                    with open(installer_path, 'wb') as f:
                        while True:
                            chunk = await response.content.read(1024 * 1024)
                            if not chunk:
                                break
                            f.write(chunk)

            if expected_sha256:
                actual_sha256 = _sha256_for_file(installer_path)
                if actual_sha256.lower() != expected_sha256.lower():
                    raise RuntimeError(
                        f"Installer checksum mismatch. Expected {expected_sha256}, got {actual_sha256}."
                    )

            return installer_path
        except Exception as e:
            logger.error(f"Failed to download installer: {e}")
            raise

    @staticmethod
    def launch_installer(installer_path: str):
        logger.info("Executing installer...")
        creationflags = (
            getattr(subprocess, "DETACHED_PROCESS", 0)
            | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        )
        subprocess.Popen(
            [installer_path, "/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART"],
            creationflags=creationflags,
            close_fds=True,
        )

    async def download_and_install(self, download_url: str, expected_sha256: str | None = None):
        """Download the installer and run it."""
        try:
            installer_path = await self.download_installer(download_url, expected_sha256)
            self.launch_installer(installer_path)

            from PyQt6.QtWidgets import QApplication
            from PyQt6.QtCore import QMetaObject, Qt

            app = QApplication.instance()
            if app:
                QMetaObject.invokeMethod(app, "quit", Qt.ConnectionType.QueuedConnection)
            return installer_path
        except Exception as e:
            logger.error(f"Failed to download and install update: {e}")
            raise
