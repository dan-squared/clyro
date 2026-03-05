from aiohttp import web
import asyncio
from threading import Thread
import logging
from PyQt6.QtCore import QMetaObject, Qt, Q_ARG
from clyro.core.types import DropIntent
from pathlib import Path

logger = logging.getLogger(__name__)

class IpcServer:
    def __init__(self, dropzone):
        self.dropzone = dropzone
        self.runner = None
        self.loop = None
        self.thread = None
        
    def start(self, port=19847):
        self.loop = asyncio.new_event_loop()
        self.thread = Thread(target=self._run_server, args=(port,), daemon=True)
        self.thread.start()
        
    def _run_server(self, port):
        asyncio.set_event_loop(self.loop)
        app = web.Application()
        app.router.add_post('/optimize', self.handle_optimize)
        app.router.add_post('/convert', self.handle_convert)
        app.router.add_post('/show', self.handle_show)
        self.runner = web.AppRunner(app)
        self.loop.run_until_complete(self.runner.setup())
        site = web.TCPSite(self.runner, 'localhost', port)
        try:
            self.loop.run_until_complete(site.start())
            logger.info(f"IPC Server running on localhost:{port}")
            self.loop.run_forever()
        except OSError as e:
            logger.warning(f"Failed to start IPC Server (port {port}): {e}. IPC commands will be unavailable.")
            # App can still run without IPC listener, just background CLI hooks won't work in this specific instance
        
    async def handle_optimize(self, request):
        data = await request.json()
        paths = [Path(p) for p in data.get('paths', [])]
        aggressive = data.get('aggressive', False)
        
        if paths:
            intent = DropIntent(mode="aggressive" if aggressive else "optimize", files=paths)
            # Must post to main thread — dropzone mutates Qt widgets
            QMetaObject.invokeMethod(
                self.dropzone, "_submit",
                Qt.ConnectionType.QueuedConnection,
                Q_ARG(object, intent)
            )
        return web.json_response({"status": "queued", "count": len(paths)})
        
    async def handle_convert(self, request):
        data = await request.json()
        paths = [Path(p) for p in data.get('paths', [])]
        fmt = data.get('target_format', 'jpg')
        
        if paths:
            intent = DropIntent(mode="convert", files=paths, target_format=fmt)
            QMetaObject.invokeMethod(
                self.dropzone, "_submit",
                Qt.ConnectionType.QueuedConnection,
                Q_ARG(object, intent)
            )
        return web.json_response({"status": "queued", "count": len(paths)})
        
    async def handle_show(self, request):
        # show() is also a UI call — dispatch to main thread
        QMetaObject.invokeMethod(
            self.dropzone, "show",
            Qt.ConnectionType.QueuedConnection
        )
        return web.json_response({"status": "shown"})

    def stop(self):
        if self.loop and self.loop.is_running():
            # Gracefully clean up aiohttp runner and pending tasks
            async def _cleanup():
                if getattr(self, 'runner', None):
                    await self.runner.cleanup()
                # Cancel all pending tasks
                tasks = [t for t in asyncio.all_tasks(self.loop) if t is not asyncio.current_task(self.loop)]
                for t in tasks:
                    t.cancel()
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)
                self.loop.stop()

            asyncio.run_coroutine_threadsafe(_cleanup(), self.loop)

        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2.0)
