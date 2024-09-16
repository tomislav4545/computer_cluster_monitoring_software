import asyncio
import tkinter as tk
from tkinter import ttk, filedialog
import threading
import json
import os
from metrics import (
    get_ssh_connection,
    close_ssh_connection,
)
from detail_window import DetailWindow
from node_card import NodeCard, FailedNodeCard
from add_edit_node_window import AddNodeWindow
import warnings
from asyncio_tkinter import AsyncTk
import nest_asyncio
nest_asyncio.apply()

warnings.filterwarnings(
    "ignore",
    category=UserWarning,
    message="Attempting to set identical low and high ylims makes transformation singular; automatically expanding.",
)

DEFAULT_CONFIG_FILE = "configs/nodes_config.json"


class App(AsyncTk):
    def __init__(self):
        super().__init__()
        self.title("Cluster Monitor")
        self.geometry("880x600")
        self.resizable(False, False)

        self.current_config_file = DEFAULT_CONFIG_FILE
        self.node_cards = []
        self.node_info_list = self.load_nodes()
        self.detail_windows = {}
        self.lock = threading.Lock()

        self.create_widgets()
        self.bind("<Configure>", self.on_resize)

        # Bind the cleanup method to the exit button and the window close event
        self.protocol("WM_DELETE_WINDOW", self.on_exit)

        # Ensure the event loop stops when the File > Exit menu is clicked
        self.file_menu.add_command(label="Exit", command=self.on_exit)

        asyncio.ensure_future(self.initialize_nodes())
        asyncio.ensure_future(self.update_cumulative_metrics())
    
    def on_exit(self):
        # Cancel all asyncio tasks
        for task in asyncio.all_tasks():
            task.cancel()

        # Stop the event loop
        self.quit()
        self._loop.stop()
        self.destroy()

    async def get_cumulative_metrics(self):
        total_memory = 0
        used_memory = 0
        total_cpu_usage = 0
        total_network_in = 0
        total_network_out = 0
        total_reads = 0
        total_writes = 0
        total_read_bytes = 0
        total_write_bytes = 0
        total_iops = 0
        normal_node_count = 0
    
        for card in self.node_cards:
            if isinstance(card, NodeCard):
                detail_window = self.detail_windows.get(card.node_info["name"])
                if detail_window and detail_window.winfo_exists():
                    metrics = detail_window.get_latest_metrics()
                    if metrics["cpu"] and metrics["memory"]:
                        total_memory += metrics["memory"]["total"]
                        used_memory += metrics["memory"]["used"]
                        total_cpu_usage += metrics["cpu"]["cpu_load"]
                        normal_node_count += 1
    
                    if metrics["network"]:
                        for interface in metrics["network"].values():
                            in_speed, out_speed = (
                                interface["bytes_in/s"],
                                interface["bytes_out/s"],
                            )
                            total_network_in += self.convert_to_kbps(in_speed)
                            total_network_out += self.convert_to_kbps(out_speed)
    
                    if metrics["diskio"]:
                        for device_metrics in metrics["diskio"].values():
                            total_reads += device_metrics["reads/s"]
                            total_writes += device_metrics["writes/s"]
                            total_read_bytes += self.convert_to_bytes(
                                device_metrics["read_bytes/s"]
                            )
                            total_write_bytes += self.convert_to_bytes(
                                device_metrics["write_bytes/s"]
                            )
                            total_iops += device_metrics["io_ops/s"]
    
        avg_cpu_usage = (
            total_cpu_usage / normal_node_count if normal_node_count > 0 else 0
        )
    
        total_memory_gb = total_memory / 1024
        used_memory_gb = used_memory / 1024
    
        return {
            "total_memory": total_memory_gb,
            "used_memory": used_memory_gb,
            "cpu_usage": avg_cpu_usage,
            "network_in": total_network_in,
            "network_out": total_network_out,
            "total_reads": total_reads,
            "total_writes": total_writes,
            "total_read_bytes": self.format_disk_io_speed(total_read_bytes),
            "total_write_bytes": self.format_disk_io_speed(total_write_bytes),
            "total_iops": total_iops,
        }

    def format_network_speed(self, speed_kbps):
        if speed_kbps >= 1024:
            return f"{speed_kbps / 1024:.2f} MB/s"
        else:
            return f"{speed_kbps:.2f} KB/s"

    def convert_to_kbps(self, speed):
        value, unit = speed.split()
        value = float(value)
        unit_multipliers = {
            "B/s": 1 / 1024,
            "KB/s": 1,
            "MB/s": 1024,
            "GB/s": 1024 * 1024,
        }
        return value * unit_multipliers[unit]

    def format_disk_io_speed(self, speed):
        if speed >= 1024**3:
            return f"{speed / 1024 ** 3:.2f} GB/s"
        elif speed >= 1024**2:
            return f"{speed / 1024 ** 2:.2f} MB/s"
        elif speed >= 1024:
            return f"{speed / 1024:.2f} KB/s"
        else:
            return f"{speed:.2f} B/s"

    def convert_to_bytes(self, value):
        value, unit = value.split()
        value = float(value)
        if unit == "KB/s":
            return value * 1024
        elif unit == "MB/s":
            return value * 1024 * 1024
        elif unit == "GB/s":
            return value * 1024 * 1024 * 1024
        return value

    def update_metrics_labels(self, metrics):
        self.cumulative_cpu_label.config(text=f"CPU Usage: {metrics['cpu_usage']:.2f}%")
        self.cumulative_memory_label.config(
            text=f"Memory: {metrics['used_memory']:.2f} GB / {metrics['total_memory']:.2f} GB"
        )
        self.cumulative_network_label.config(
            text=f"Network In: {self.format_network_speed(metrics['network_in'])}, Out: {self.format_network_speed(metrics['network_out'])}"
        )
        self.cumulative_diskio_label.config(
            text=f"Disk I/O - Reads/s: {metrics['total_reads']:.2f} , Writes/s: {metrics['total_writes']:.2f} , "
            f"Read Bytes: {metrics['total_read_bytes']}, Write Bytes: {metrics['total_write_bytes']} "
            f"IOPS: {metrics['total_iops']}"
        )

    async def update_cumulative_metrics(self):
        while True:
            try:
                metrics = await self.get_cumulative_metrics()
                if metrics:
                    self.after(0, self.update_metrics_labels, metrics)
            except Exception as e:
                print(f"Error updating metrics: {e}")
            await asyncio.sleep(1)
            
    def load_nodes(self):
        try:
            if not os.path.exists(self.current_config_file):
                return []

            with open(self.current_config_file, "r") as f:
                nodes = json.load(f)
                if not nodes:
                    return []
                return nodes
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def save_nodes(self):
        with open(self.current_config_file, "w") as f:
            json.dump(self.node_info_list, f, indent=4)

    def create_widgets(self):
        self.menu_bar = tk.Menu(self)
        self.config(menu=self.menu_bar)

        self.file_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="File", menu=self.file_menu)
        self.file_menu.add_command(
            label="Load Config File", command=self.load_config_file
        )
        self.file_menu.add_command(
            label="Save Config File As", command=self.save_config_as
        )
        self.file_menu.add_command(
            label="Create New Empty Config File", command=self.create_new_config
        )
        self.file_menu.add_separator()

        self.cumulative_memory_label = tk.Label(self, text="Memory: N/A")
        self.cumulative_memory_label.pack()

        self.cumulative_cpu_label = tk.Label(self, text="CPU Usage: N/A")
        self.cumulative_cpu_label.pack()

        self.cumulative_network_label = tk.Label(self, text="Network In: N/A, Out: N/A")
        self.cumulative_network_label.pack()

        self.cumulative_diskio_label = tk.Label(
            self,
            text="Disk I/O - Reads: N/A, Writes: N/A, Read Bytes: N/A, Write Bytes: N/A, IOPS: N/A",
        )
        self.cumulative_diskio_label.pack()

        self.add_button = tk.Button(self, text="Add Node", command=self.add_node)
        self.add_button.pack()

        self.canvas = tk.Canvas(self)
        self.scrollbar = ttk.Scrollbar(
            self, orient="vertical", command=self.canvas.yview
        )
        self.scrollable_frame = ttk.Frame(self.canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.grid_frame = ttk.Frame(self.scrollable_frame)
        self.grid_frame.grid(sticky="nsew")
        self.grid_frame.columnconfigure(0, weight=1)
        self.grid_frame.rowconfigure(0, weight=1)

    async def initialize_nodes(self):
        self.node_info_list.sort(key=lambda x: x["name"].lower())
        for node_info in self.node_info_list:
            await self.add_node_card(node_info)

    async def add_node_card(self, node_info):
        card_width = 200
        card_height = 150
        ssh_client, connected = await get_ssh_connection(node_info)
        if connected:
            card = NodeCard(
                self.grid_frame,
                self,
                node_info,
                self.show_details,
                self.remove_node,
                self.update_node_info,
                self.handle_failed_node,
                width=card_width,
                height=card_height,
            )
            self.node_cards.append(card)
            self.refresh_grid()
            if node_info["name"] not in self.detail_windows:
                self.detail_windows[node_info["name"]] = DetailWindow(self, node_info)
        else:
            card = FailedNodeCard(
                self.grid_frame,
                self,
                node_info,
                self.reconnect_node,
                self.update_node_info,
                self.remove_node,
                width=card_width,
                height=card_height,
            )
            self.node_cards.append(card)
            self.refresh_grid()

    async def reconnect_node(self, node_info):
        await close_ssh_connection(node_info)

        ssh_client, connected = await get_ssh_connection(node_info)
        if connected:
            self.replace_failed_node_with_normal_node(node_info)
        return connected

    def handle_failed_node(self, node_card):
        with self.lock:
            node_info = node_card.node_info
            print(f"Handling failed node: {node_info['name']}")
    
            if node_card in self.node_cards:
                node_card.destroy()
                self.node_cards.remove(node_card)
                if node_info["name"] in self.detail_windows:
                    self.detail_windows[node_info["name"]].destroy()
                    del self.detail_windows[node_info["name"]]
                failed_card = FailedNodeCard(
                    self.grid_frame,
                    self,
                    node_info,
                    self.reconnect_node,
                    self.update_node_info,
                    self.remove_node,
                )
                failed_card.grid(padx=10, pady=10, sticky="nsew")
                self.node_cards.append(failed_card)
                self.refresh_grid()
            else:
                print(f"Node card for {node_info['name']} is not in the node_cards list.")



    def replace_failed_node_with_normal_node(self, node_info):
        with self.lock:
            failed_node_card = None
            for card in self.node_cards:
                if isinstance(card, FailedNodeCard) and card.node_info == node_info:
                    failed_node_card = card
                    break

            if failed_node_card:
                print(f"Replacing failed node with normal node: {node_info['name']}")
                failed_node_card.destroy()
                self.node_cards.remove(failed_node_card)
                card = NodeCard(
                    self.grid_frame,
                    self,
                    node_info,
                    self.show_details,
                    self.remove_node,
                    self.update_node_info,
                    self.handle_failed_node,
                    width=200,
                    height=150,
                )
                card.failed_connection_attempts = 0  # Reset connection attempts counter
                self.node_cards.append(card)
                self.refresh_grid()
                #asyncio.ensure_future(self.add_node_card(node_info))
                if node_info["name"] not in self.detail_windows:
                    self.detail_windows[node_info["name"]] = DetailWindow(self, node_info)

    def update_node_info(self, old_info, new_info):
        for node in self.node_info_list:
            if node == old_info:
                node.update(new_info)

        self.save_nodes()

        close_ssh_connection(old_info)

        if old_info["name"] in self.detail_windows:
            self.detail_windows[old_info["name"]].destroy()
            del self.detail_windows[old_info["name"]]

        reconnected = self.reconnect_node(new_info)

        for card in self.node_cards:
            if card.node_info == old_info:
                if reconnected:
                    if isinstance(card, FailedNodeCard):
                        self.replace_failed_node_with_normal_node(card)
                    else:
                        card.update_display(new_info)
                else:
                    self.handle_failed_node(card)

        if reconnected:
            self.detail_windows[new_info["name"]] = DetailWindow(self, new_info)

        self.refresh_nodes()

    def remove_node(self, node_info):
        self.node_info_list = [
            node for node in self.node_info_list if node != node_info
        ]
        close_ssh_connection(node_info)
        self.save_nodes()
        self.refresh_nodes()

    def add_node(self):
        new_node_window = AddNodeWindow(self)

    def clear_nodes(self):
        for card in self.node_cards:
            card.destroy()
        self.node_cards.clear()

        for window in self.detail_windows.values():
            window.destroy()
        self.detail_windows.clear()

    def load_config_file(self):
        file_path = filedialog.askopenfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if file_path:
            self.clear_nodes()
            self.current_config_file = file_path
            self.node_info_list = self.load_nodes()
            self.node_info_list.sort(key=lambda x: x["name"].lower())
            asyncio.ensure_future(self.initialize_nodes())
            self.refresh_grid()

    def save_config_as(self):
        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if file_path:
            self.current_config_file = file_path
            self.save_nodes()

    def create_new_config(self):
        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if file_path:
            with open(file_path, "w") as f:
                f.write("[]")
            self.current_config_file = file_path
            self.node_info_list = []
            self.refresh_nodes()

    def refresh_nodes(self):
        existing_node_names = {card.node_info["name"] for card in self.node_cards}
        updated_node_names = {node_info["name"] for node_info in self.node_info_list}

        for card in self.node_cards[:]:
            if card.node_info["name"] not in updated_node_names:
                card.destroy()
                self.node_cards.remove(card)

        nodes_needing_cards = [
            node_info
            for node_info in self.node_info_list
            if node_info["name"] not in existing_node_names
        ]
        nodes_needing_cards.sort(key=lambda x: x["name"].lower())

        for node_info in nodes_needing_cards:
            asyncio.ensure_future(self.add_node_card(node_info))

        if hasattr(self, "empty_label") and self.node_info_list:
            self.empty_label.destroy()

        if not self.node_info_list:
            self.empty_label = tk.Label(
                self.grid_frame,
                text="No configuration file found or it is empty. Please add a node.",
            )
            self.empty_label.grid(row=0, column=0, padx=10, pady=10)

        self.refresh_grid()

    def refresh_grid(self):
        card_width = 200
        card_height = 150
        num_columns = max(1, self.winfo_width() // (card_width + 20))
        num_rows = (len(self.node_cards) + num_columns - 1) // num_columns

        for idx, card in enumerate(self.node_cards):
            row, col = divmod(idx, num_columns)
            card.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")
            card.grid_propagate(False)

        for row in range(num_rows):
            self.grid_frame.rowconfigure(row, weight=1, minsize=card_height)
        for col in range(num_columns):
            self.grid_frame.columnconfigure(col, weight=1, minsize=card_width)

    def on_resize(self, event):
        self.refresh_grid()

    def show_details(self, node_info):
        detail_window = self.detail_windows[node_info["name"]]
        detail_window.deiconify()
        detail_window.lift()
        #detail_window.state("zoomed")

    def on_close_detail_window(self, node_info):
        self.detail_windows[node_info["name"]].withdraw()