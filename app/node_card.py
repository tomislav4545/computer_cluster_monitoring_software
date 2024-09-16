import tkinter as tk
import asyncio
from metrics import collect_nodecard_metrics
from add_edit_node_window import EditNodeWindow

class NodeCard(tk.Frame):
    def __init__(
        self,
        parent,
        app,
        node_info,
        on_click,
        on_remove,
        on_edit,
        on_fail,
        width=200,
        height=150,
    ):
        super().__init__(
            parent,
            bd=2,
            relief=tk.SOLID,
            padx=10,
            pady=10,
            width=width,
            height=height,
            highlightbackground="green",
            highlightcolor="green",
            highlightthickness=2,
        )
        self.app = app
        self.node_info = node_info
        self.on_click = on_click
        self.on_remove = on_remove
        self.on_edit = on_edit
        self.on_fail = on_fail
        self.failed_attempts = 0
        self.max_failed_attempts = 20
        self.failed = False

        self.config(width=width, height=height)
        self.grid_propagate(False)

        self.label = tk.Label(
            self, text=node_info["name"], font=("Arial", 14), wraplength=width - 20
        )
        self.label.pack()

        self.cpu_label = tk.Label(self, text="CPU: N/A", font=("Arial", 12))
        self.cpu_label.pack()

        self.memory_label = tk.Label(self, text="Memory: N/A", font=("Arial", 12))
        self.memory_label.pack()

        self.update_button = tk.Button(
            self, text="More Info", command=self.show_details
        )
        self.update_button.pack()

        self.edit_button = tk.Button(self, text="Edit", command=self.edit_node)
        self.edit_button.pack()

        self.remove_button = tk.Button(self, text="Remove", command=self.remove_node)
        self.remove_button.pack()

        self.schedule_update()

    def schedule_update(self):
        self.update_metrics()
        self.after(1000, self.schedule_update)

    def update_metrics(self):
        if self.failed:  # Do not update metrics if the node has failed
            return

        async def fetch_metrics():
            try:
                cpu_usage, memory_usage = await collect_nodecard_metrics(self.node_info)
                if cpu_usage is None or memory_usage is None:
                    raise Exception("Failed to fetch metrics")
                self.cpu_label.config(text=f"CPU: {cpu_usage}%")
                self.memory_label.config(text=f"Memory: {memory_usage}%")
                self.failed_attempts = 0
            except Exception as e:
                print(f"Error fetching metrics for {self.node_info['name']}: {e}")
                self.failed_attempts += 1
                if self.failed_attempts >= self.max_failed_attempts:
                    self.failed = True
                    self.after(0, self.on_fail, self)

        asyncio.ensure_future(fetch_metrics())

    def show_details(self):
        self.on_click(self.node_info)

    def edit_node(self):
        EditNodeWindow(self.app, self.node_info, self.on_edit)

    def remove_node(self):
        self.on_remove(self.node_info)
        self.destroy()

    def update_display(self, updated_info):
        self.node_info.update(updated_info)
        self.label.config(text=updated_info["name"])


class FailedNodeCard(tk.Frame):
    def __init__(
        self,
        parent,
        app,
        node_info,
        on_reconnect,
        on_edit,
        on_remove,
        width=200,
        height=150,
    ):
        super().__init__(
            parent,
            bd=2,
            relief=tk.SOLID,
            padx=10,
            pady=10,
            width=width,
            height=height,
            highlightbackground="red",
            highlightcolor="red",
            highlightthickness=2,
        )
        self.app = app
        self.node_info = node_info
        self.on_reconnect = on_reconnect
        self.on_edit = on_edit
        self.on_remove = on_remove

        self.config(width=width, height=height)
        self.grid_propagate(False)

        self.label = tk.Label(
            self,
            text=f"{node_info['name']} (Connection failed)",
            font=("Arial", 14),
            wraplength=width - 20,
        )
        self.label.pack()

        self.reconnect_button = tk.Button(
            self, text="Reconnect", command=lambda: asyncio.create_task(self.reconnect_node())
        )
        self.reconnect_button.pack()

        self.edit_button = tk.Button(self, text="Edit", command=self.edit_node)
        self.edit_button.pack()

        self.remove_button = tk.Button(self, text="Remove", command=self.remove_node)
        self.remove_button.pack()

    async def reconnect_node(self):
        connected = await self.on_reconnect(self.node_info)
        if connected:
            self.app.replace_failed_node_with_normal_node(self.node_info)

    def edit_node(self):
        EditNodeWindow(self.app, self.node_info, self.on_edit)

    def remove_node(self):
        self.on_remove(self.node_info)
        self.destroy()

    def update_display(self, updated_info):
        self.node_info.update(updated_info)
        self.label.config(text=f"{updated_info['name']} (Connection failed)")