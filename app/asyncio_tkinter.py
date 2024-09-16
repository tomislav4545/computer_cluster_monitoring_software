import asyncio
import tkinter as tk

class AsyncTk:
    def __init__(self, interval=0.05):
        self._root = tk.Tk()
        self._interval = interval
        self._loop = asyncio.get_event_loop()
        self._loop.create_task(self._periodic_call())
    
    async def _periodic_call(self):
        while True:
            self._root.update()
            await asyncio.sleep(self._interval)
    
    def mainloop(self):
        try:
            self._loop.run_forever()
        except KeyboardInterrupt:
            pass
        finally:
            self._loop.run_until_complete(self._loop.shutdown_asyncgens())
            self._loop.close()
    
    def __getattr__(self, name):
        return getattr(self._root, name)
    
    def __setattr__(self, name, value):
        if name in ["_root", "_interval", "_loop"]:
            super().__setattr__(name, value)
        else:
            setattr(self._root, name, value)
    
    def __del__(self):
        self._loop.run_until_complete(self._loop.shutdown_asyncgens())
        self._loop.close()

# Use AsyncTk instead of ThemedTk in your application.
