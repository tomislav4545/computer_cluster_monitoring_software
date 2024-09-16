import asyncio
import tkinter as tk
from tkinter import ttk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from metrics import (
    collect_system_info,
    collect_diskio_metrics,
    collect_cpu_metrics,
    collect_disk_metrics,
    collect_memory_metrics,
    collect_network_metrics
)
import datetime

class DetailWindow(tk.Toplevel):
    def __init__(self, parent, node_info):
        super().__init__(parent)
        self.node_info = node_info
        self.title(f"Details for {node_info['name']}")

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        self.disk_notebook = None
        self.network_notebook = None

        self.metric_data = {}
        self.timestamps = {}
        self.metric_plots = {}
        self.disk_widgets = {}
        self.memory_widgets = {}
        self.network_widgets = {}
        self.diskio_widgets = {}

        self.latest_cpu_metrics = None
        self.latest_memory_metrics = None
        self.latest_network_metrics = None
        self.latest_diskio_metrics = None

        self.create_tabs()
        self.initialize_graphs()

        asyncio.create_task(self.update_graphs())

        self.protocol("WM_DELETE_WINDOW", self.on_close_window)
        self.maximize_window()
        self.withdraw()
    
    def maximize_window(self):
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        self.geometry(f"{screen_width}x{screen_height}+0+0")

    def create_tabs(self):
        self.create_cpu_tab()
        self.create_memory_tab()
        self.create_network_tab()
        self.create_disk_tab()
        self.create_diskio_tab()
        self.create_system_tab()

    def create_system_tab(self):
        system_frame = ttk.Frame(self.notebook)
        self.notebook.add(system_frame, text="System")

        asyncio.create_task(self.display_system_info(system_frame))

    async def display_system_info(self, system_frame):
        system_info = await collect_system_info(self.node_info)

        if system_info is None:
            error_label = tk.Label(system_frame, text="Failed to retrieve system information", font=("Helvetica", 12), fg="red")
            error_label.pack(fill=tk.BOTH, expand=True)
            return

        info_text = "\n".join(
            [f"{self.format_key(key)}: {value}" for key, value in system_info.items()]
        )
        system_label = tk.Label(system_frame, justify="left", font=("Helvetica", 12))
        system_label.pack(fill=tk.BOTH, expand=True)
        for key, value in system_info.items():
            key_label = tk.Label(
                system_label,
                text=self.format_key(key) + ":",
                font=("Helvetica", 12, "bold"),
            )
            key_label.grid(sticky="w", padx=5)
            value_label = tk.Label(system_label, text=value, font=("Helvetica", 12))
            value_label.grid(sticky="w", padx=5)

    def format_key(self, key):
        formatted_key = key.replace("_", " ").title()
        return formatted_key

    def create_cpu_tab(self):
        cpu_metrics = [
            "cpu_load",
            "cpu_user",
            "cpu_nice",
            "cpu_system",
            "cpu_iowait",
            "cpu_irq",
            "cpu_softirq",
            "load_avg_1min",
            "load_avg_5min",
            "load_avg_15min",
        ]

        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="CPU")

        num_columns = 2
        num_rows = (len(cpu_metrics) + 1) // num_columns

        fig, axes = plt.subplots(num_rows, num_columns, figsize=(10, 3 * num_rows))
        axes = axes.flatten()

        for ax, metric in zip(axes, cpu_metrics):
            ax.set_title(metric.replace("_", " ").title())
            if metric.startswith("load_avg"):
                ax.set_ylim(0, None)
            else:
                ax.set_ylim(0, 100)
            self.metric_plots[metric] = ax
            self.metric_data[metric] = [0]
            self.timestamps[metric] = [0]

        for i in range(len(cpu_metrics), len(axes)):
            axes[i].axis("off")

        fig.tight_layout()
        canvas = FigureCanvasTkAgg(fig, frame)
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        self.cpu_canvas = canvas
        self.cpu_fig = fig

    def create_disk_tab(self):
        disk_frame = ttk.Frame(self.notebook)
        self.notebook.add(disk_frame, text="Disk")

        self.disk_notebook = ttk.Notebook(disk_frame)
        self.disk_notebook.pack(fill=tk.BOTH, expand=True)

    def create_memory_tab(self):
        memory_frame = ttk.Frame(self.notebook)
        self.notebook.add(memory_frame, text="Memory")

        self.memory_notebook = ttk.Notebook(memory_frame)
        self.memory_notebook.pack(fill=tk.BOTH, expand=True)

    def create_network_tab(self):
        network_frame = ttk.Frame(self.notebook)
        self.notebook.add(network_frame, text="Network")

        self.network_notebook = ttk.Notebook(network_frame)
        self.network_notebook.pack(fill=tk.BOTH, expand=True)

    def create_diskio_tab(self):
        diskio_frame = ttk.Frame(self.notebook)
        self.notebook.add(diskio_frame, text="Disk I/O")

        self.diskio_notebook = ttk.Notebook(diskio_frame)
        self.diskio_notebook.pack(fill=tk.BOTH, expand=True)

    def initialize_graphs(self):
        for metric, ax in self.metric_plots.items():
            ax.clear()
            ax.set_ylim(0, 100)
            ax.plot(
                self.timestamps[metric],
                self.metric_data[metric],
                label=metric.replace("_", " ").title(),
            )
            ax.legend()
            ax.set_title(metric.replace("_", " ").title())
            ax.set_xticks(self.timestamps[metric])
            ax.set_xticklabels(["00:00:00"])
            ax.set_xlim(left=0, right=1)

        self.cpu_fig.autofmt_xdate()
        self.cpu_fig.canvas.draw()

        asyncio.create_task(self.update_disk_metrics(initial=True))
        asyncio.create_task(self.update_memory_metrics(initial=True))
        asyncio.create_task(self.update_network_metrics(initial=True))
        asyncio.create_task(self.update_diskio_metrics(initial=True))

    async def update_graphs(self):
        async def update_fast_metrics():
            while True:
                try:
                    if self.winfo_exists():
                        await asyncio.gather(
                            self.update_cpu_metrics(),
                            self.update_memory_metrics(),
                            self.update_disk_metrics()
                        )
                except Exception as e:
                    print(f"Error updating fast metrics: {e}")
                await asyncio.sleep(1)

        async def update_slow_metrics():
            while True:
                try:
                    if self.winfo_exists():
                        await asyncio.gather(
                            self.update_network_metrics(),
                            self.update_diskio_metrics()
                        )
                except Exception as e:
                    print(f"Error updating slow metrics: {e}")
                await asyncio.sleep(3)

        fast_task = asyncio.create_task(update_fast_metrics())
        slow_task = asyncio.create_task(update_slow_metrics())

        await asyncio.gather(fast_task, slow_task)
    
    """ async def update_graphs(self):
        while True:
            try:
                if self.winfo_exists():
                    await asyncio.gather(
                        self.update_cpu_metrics(),
                        self.update_memory_metrics(),
                        self.update_network_metrics(),
                        self.update_disk_metrics(),
                        self.update_diskio_metrics()
                    )
                    await asyncio.sleep(1)
            except Exception as e:
                print(f"Error updating graphs: {e}")
            await asyncio.sleep(0.1) """

    async def update_cpu_metrics(self):
        if not self.winfo_exists():
            return

        system_time_str, cpu_metrics = await collect_cpu_metrics(self.node_info)
        if system_time_str is None or cpu_metrics is None:
            print(f"Failed to update network metrics for {self.node_info['name']}")
            return
        self.latest_cpu_metrics = cpu_metrics
        h, m, s = map(int, system_time_str.split(":"))
        system_time = h * 3600 + m * 60 + s

        metrics = [
            "cpu_load",
            "cpu_user",
            "cpu_nice",
            "cpu_system",
            "cpu_iowait",
            "cpu_irq",
            "cpu_softirq",
            "load_avg_1min",
            "load_avg_5min",
            "load_avg_15min",
        ]

        for metric in metrics:
            if metric in cpu_metrics:
                value = cpu_metrics.get(metric, 0)
                self.metric_data[metric].append(value)
                self.timestamps[metric].append(system_time)

                ten_minutes_ago = system_time - 600

                while (
                    self.timestamps[metric]
                    and self.timestamps[metric][0] < ten_minutes_ago
                ):
                    self.timestamps[metric].pop(0)
                    self.metric_data[metric].pop(0)

                ax = self.metric_plots[metric]
                ax.clear()
                ax.set_title(metric.replace("_", " ").title())
                ax.plot(
                    self.timestamps[metric],
                    self.metric_data[metric],
                    label=metric.replace("_", " ").title(),
                )
                ax.legend()

                if metric.startswith("load_avg"):
                    ax.set_ylim(0, 4)
                else:
                    ax.set_ylim(0, 100)

                formatted_times = [
                    datetime.timedelta(seconds=t).seconds
                    for t in self.timestamps[metric]
                ]
                formatted_times = [
                    datetime.time(t // 3600, (t % 3600) // 60, t % 60).strftime(
                        "%H:%M:%S"
                    )
                    for t in formatted_times
                ]
                ax.set_xticks(self.timestamps[metric][::30])
                ax.set_xticklabels(formatted_times[::30])
                ax.set_xlim(left=ten_minutes_ago, right=system_time)

        self.cpu_fig.autofmt_xdate()
        self.cpu_fig.canvas.draw()

    async def update_disk_metrics(self, initial=False):
        if not self.winfo_exists():
            return

        system_time_str, disk_metrics = await collect_disk_metrics(self.node_info)
        if system_time_str is None or disk_metrics is None:
            print(f"Failed to update disk metrics for {self.node_info['name']}")
            return
        self.latest_disk_metrics = disk_metrics
        h, m, s = map(int, system_time_str.split(":"))
        system_time = h * 3600 + m * 60 + s

        if initial:
            for fs in disk_metrics:
                disk_frame = ttk.Frame(self.disk_notebook)
                self.disk_notebook.add(disk_frame, text=fs["filesystem"])

                fig, ax = plt.subplots(figsize=(3, 1))
                canvas = FigureCanvasTkAgg(fig, disk_frame)
                canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

                fig3, ax3 = plt.subplots(figsize=(5, 1))
                canvas3 = FigureCanvasTkAgg(fig3, disk_frame)
                canvas3.get_tk_widget().pack(fill=tk.BOTH, expand=True)

                self.disk_widgets[fs["filesystem"]] = {
                    "frame": disk_frame,
                    "canvas": canvas,
                    "fig": fig,
                    "ax": ax,
                    "canvas3": canvas3,
                    "fig3": fig3,
                    "ax3": ax3,
                    "timestamps": [],
                    "usage_percent": [],
                }

        for fs in disk_metrics:
            widget = self.disk_widgets.get(fs["filesystem"])
            if widget:
                ax = widget["ax"]
                ax.clear()
                ax.pie(
                    [
                        float(fs["used"].strip("G").strip("M").strip("K")),
                        float(fs["available"].strip("G").strip("M").strip("K")),
                    ],
                    labels=["Used", "Available"],
                    autopct="%1.1f%%",
                    colors=["red", "green"],
                )
                ax.set_title(f"Usage of {fs['filesystem']}")
                widget["fig"].canvas.draw()

                widget["timestamps"].append(system_time)
                widget["usage_percent"].append(int(fs["use_percent"].strip("%")))

                while (
                    widget["timestamps"] and widget["timestamps"][0] < system_time - 600
                ):
                    widget["timestamps"].pop(0)
                    widget["usage_percent"].pop(0)

                ax3 = widget["ax3"]
                ax3.clear()
                ax3.plot(widget["timestamps"], widget["usage_percent"], label="Usage %")
                ax3.set_title(f"Usage % over Time for {fs['filesystem']}")
                ax3.legend()
                ax3.set_ylim(0, 100)
                ax3.set_xlim(left=max(0, system_time - 600))

                formatted_times = [
                    datetime.datetime.fromtimestamp(t).strftime("%H:%M:%S")
                    for t in widget["timestamps"]
                ]
                ax3.set_xticks(widget["timestamps"][::10])
                ax3.set_xticklabels(formatted_times[::10], rotation=45)
                widget["fig3"].canvas.draw()

    async def update_diskio_metrics(self, initial=False):
        if not self.winfo_exists():
            return

        system_time_str, diskio_metrics = await collect_diskio_metrics(self.node_info)
        if system_time_str is None or diskio_metrics is None:
            print(f"Failed to update network metrics for {self.node_info['name']}")
            return
        self.latest_diskio_metrics = diskio_metrics
        h, m, s = map(int, system_time_str.split(":"))
        system_time = h * 3600 + m * 60 + s

        if initial:
            for device in diskio_metrics:
                diskio_frame = ttk.Frame(self.diskio_notebook)
                self.diskio_notebook.add(diskio_frame, text=device)

                figs, axs = plt.subplots(5, 1, figsize=(8, 10))
                canvas = FigureCanvasTkAgg(figs, diskio_frame)
                canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

                self.diskio_widgets[device] = {
                    "frame": diskio_frame,
                    "canvas": canvas,
                    "figs": figs,
                    "axs": axs,
                    "timestamps": [],
                    "reads": [],
                    "writes": [],
                    "read_bytes": [],
                    "write_bytes": [],
                    "io_ops": [],
                }

        for device, metrics in diskio_metrics.items():
            widget = self.diskio_widgets.get(device)
            if widget:
                widget["timestamps"].append(system_time)
                widget["reads"].append(metrics["reads/s"])
                widget["writes"].append(metrics["writes/s"])
                widget["read_bytes"].append(
                    self.convert_to_bytes(metrics["read_bytes/s"])
                )
                widget["write_bytes"].append(
                    self.convert_to_bytes(metrics["write_bytes/s"])
                )
                widget["io_ops"].append(metrics["io_ops/s"])

                while (
                    widget["timestamps"] and widget["timestamps"][0] < system_time - 600
                ):
                    widget["timestamps"].pop(0)
                    widget["reads"].pop(0)
                    widget["writes"].pop(0)
                    widget["read_bytes"].pop(0)
                    widget["write_bytes"].pop(0)
                    widget["io_ops"].pop(0)

                for idx, metric in enumerate(
                    ["reads", "writes", "read_bytes", "write_bytes", "io_ops"]
                ):
                    ax = widget["axs"][idx]
                    ax.clear()

                    if metric in ["read_bytes", "write_bytes"]:
                        max_value = max(widget[metric])
                        unit, divisor = self.determine_unit(max_value)
                        scaled_values = [v / divisor for v in widget[metric]]
                    else:
                        scaled_values = widget[metric]
                        unit = ""

                    ax.plot(
                        widget["timestamps"], scaled_values, label=f"{metric}/s {unit}"
                    )
                    ax.set_title(f"{metric.replace('_', ' ').title()} over Time")
                    ax.legend()
                    ax.set_xlim(left=max(0, system_time - 600))

                    formatted_times = [
                        datetime.datetime.fromtimestamp(t).strftime("%H:%M:%S")
                        for t in widget["timestamps"]
                    ]
                    ax.set_xticks(widget["timestamps"][::10])
                    ax.set_xticklabels(formatted_times[::10], rotation=45)

                widget["figs"].tight_layout()
                widget["canvas"].draw()

    async def update_memory_metrics(self, initial=False):
        if not self.winfo_exists():
            return

        system_time_str, memory_metrics, swap_metrics = await collect_memory_metrics(
            self.node_info
        )
        if system_time_str is None or memory_metrics is None or swap_metrics is None:
            print(f"Failed to update memory metrics for {self.node_info['name']}")
            return
        self.latest_memory_metrics = memory_metrics
        h, m, s = map(int, system_time_str.split(":"))
        system_time = h * 3600 + m * 60 + s
        if initial:
            memory_frame = ttk.Frame(self.memory_notebook)
            self.memory_notebook.add(memory_frame, text="Memory")

            fig_memory, ax_memory = plt.subplots(figsize=(6, 2))
            canvas_memory = FigureCanvasTkAgg(fig_memory, memory_frame)
            canvas_memory.get_tk_widget().pack(fill=tk.BOTH, expand=True)

            fig_memory_usage, ax_memory_usage = plt.subplots(figsize=(8, 2))
            canvas_memory_usage = FigureCanvasTkAgg(fig_memory_usage, memory_frame)
            canvas_memory_usage.get_tk_widget().pack(fill=tk.BOTH, expand=True)

            swap_frame = ttk.Frame(self.memory_notebook)
            self.memory_notebook.add(swap_frame, text="Swap")

            fig_swap, ax_swap = plt.subplots(figsize=(6, 2))
            canvas_swap = FigureCanvasTkAgg(fig_swap, swap_frame)
            canvas_swap.get_tk_widget().pack(fill=tk.BOTH, expand=True)

            fig_swap_usage, ax_swap_usage = plt.subplots(figsize=(8, 2))
            canvas_swap_usage = FigureCanvasTkAgg(fig_swap_usage, swap_frame)
            canvas_swap_usage.get_tk_widget().pack(fill=tk.BOTH, expand=True)

            self.memory_widgets = {
                "frame": memory_frame,
                "canvas_memory": canvas_memory,
                "fig_memory": fig_memory,
                "ax_memory": ax_memory,
                "canvas_memory_usage": canvas_memory_usage,
                "fig_memory_usage": fig_memory_usage,
                "ax_memory_usage": ax_memory_usage,
                "swap_frame": swap_frame,
                "canvas_swap": canvas_swap,
                "fig_swap": fig_swap,
                "ax_swap": ax_swap,
                "canvas_swap_usage": canvas_swap_usage,
                "fig_swap_usage": fig_swap_usage,
                "ax_swap_usage": ax_swap_usage,
                "memory_timestamps": [],
                "memory_used_percent": [],
                "swap_timestamps": [],
                "swap_used_percent": [],
            }

        widget = self.memory_widgets

        ax_memory = widget["ax_memory"]
        ax_memory.clear()
        ax_memory.pie(
            [memory_metrics["used_percent"], 100 - memory_metrics["used_percent"]],
            labels=["Used", "Free"],
            autopct="%1.1f%%",
            colors=["red", "green"],
        )
        ax_memory.set_title("Memory Usage")
        widget["fig_memory"].canvas.draw()
        plt.close(widget["fig_memory"])

        widget["memory_timestamps"].append(system_time)
        widget["memory_used_percent"].append(memory_metrics["used_percent"])

        while (
            widget["memory_timestamps"]
            and widget["memory_timestamps"][0] < system_time - 600
        ):
            widget["memory_timestamps"].pop(0)
            widget["memory_used_percent"].pop(0)

        ax_memory_usage = widget["ax_memory_usage"]
        ax_memory_usage.clear()
        ax_memory_usage.plot(
            widget["memory_timestamps"], widget["memory_used_percent"], label="Usage %"
        )
        ax_memory_usage.set_title("Memory Usage % over Time")
        ax_memory_usage.legend()
        ax_memory_usage.set_ylim(0, 100)
        ax_memory_usage.set_xlim(left=max(0, system_time - 600), right=system_time)

        formatted_times = [
            datetime.datetime.fromtimestamp(t).strftime("%H:%M:%S")
            for t in widget["memory_timestamps"]
        ]

        label_step = 30
        ax_memory_usage.set_xticks(widget["memory_timestamps"][::label_step])
        ax_memory_usage.set_xticklabels(formatted_times[::label_step], rotation=45)
        widget["fig_memory_usage"].canvas.draw()

        ax_swap = widget["ax_swap"]
        ax_swap.clear()
        ax_swap.pie(
            [swap_metrics["used_percent"], 100 - swap_metrics["used_percent"]],
            labels=["Used", "Free"],
            autopct="%1.1f%%",
            colors=["red", "green"],
        )
        ax_swap.set_title("Swap Usage")
        widget["fig_swap"].canvas.draw()
        plt.close(widget["fig_swap"])

        widget["swap_timestamps"].append(system_time)
        widget["swap_used_percent"].append(swap_metrics["used_percent"])

        while (
            widget["swap_timestamps"]
            and widget["swap_timestamps"][0] < system_time - 600
        ):
            widget["swap_timestamps"].pop(0)
            widget["swap_used_percent"].pop(0)

        ax_swap_usage = widget["ax_swap_usage"]
        ax_swap_usage.clear()
        ax_swap_usage.plot(
            widget["swap_timestamps"], widget["swap_used_percent"], label="Usage %"
        )
        ax_swap_usage.set_title("Swap Usage % over Time")
        ax_swap_usage.legend()
        ax_swap_usage.set_ylim(0, 100)
        ax_swap_usage.set_xlim(left=max(0, system_time - 600), right=system_time)

        formatted_times_swap = [
            datetime.datetime.fromtimestamp(t).strftime("%H:%M:%S")
            for t in widget["swap_timestamps"]
        ]

        ax_swap_usage.set_xticks(widget["swap_timestamps"][::label_step])
        ax_swap_usage.set_xticklabels(formatted_times_swap[::label_step], rotation=45)
        widget["fig_swap_usage"].canvas.draw()

    async def update_network_metrics(self, initial=False):
        if not self.winfo_exists():
            return

        system_time_str, network_metrics = await collect_network_metrics(self.node_info)
        if system_time_str is None or network_metrics is None:
            print(f"Failed to update network metrics for {self.node_info['name']}")
            return
        self.latest_network_metrics = network_metrics
        h, m, s = map(int, system_time_str.split(":"))
        system_time = h * 3600 + m * 60 + s

        def custom_sort(interface):
            if interface.startswith("eth"):
                return (0, interface)
            elif interface.startswith("enp"):
                return (1, interface)
            elif interface.startswith("wlan"):
                return (2, interface)
            else:
                return (3, interface)

        controller_order = sorted(network_metrics.keys(), key=custom_sort)

        if initial:
            for interface in controller_order:
                network_frame = ttk.Frame(self.network_notebook)
                self.network_notebook.add(network_frame, text=interface)

                fig, (ax_in, ax_out) = plt.subplots(2, 1, figsize=(5, 2), sharex=True)
                canvas_in = FigureCanvasTkAgg(fig, network_frame)
                canvas_in.get_tk_widget().pack(fill=tk.BOTH, expand=True)

                self.network_widgets[interface] = {
                    "frame": network_frame,
                    "canvas_in": canvas_in,
                    "fig": fig,
                    "ax_in": ax_in,
                    "ax_out": ax_out,
                    "timestamps": [],
                    "bytes_in": [],
                    "bytes_out": [],
                }

        for interface in controller_order:
            metrics = network_metrics.get(interface, None)
            if metrics:
                widget = self.network_widgets.get(interface)
                if widget:
                    widget["timestamps"].append(system_time)
                    bytes_in = self.convert_to_bytes(metrics["bytes_in/s"])
                    bytes_out = self.convert_to_bytes(metrics["bytes_out/s"])
                    widget["bytes_in"].append(bytes_in)
                    widget["bytes_out"].append(bytes_out)

                    while (
                        widget["timestamps"]
                        and widget["timestamps"][0] < system_time - 600
                    ):
                        widget["timestamps"].pop(0)
                        widget["bytes_in"].pop(0)
                        widget["bytes_out"].pop(0)

                    ax_in = widget["ax_in"]
                    ax_out = widget["ax_out"]
                    ax_in.clear()
                    ax_out.clear()

                    unit_in, divisor_in = self.determine_unit(max(widget["bytes_in"]))
                    unit_out, divisor_out = self.determine_unit(
                        max(widget["bytes_out"])
                    )
                    scaled_bytes_in = [b / divisor_in for b in widget["bytes_in"]]
                    scaled_bytes_out = [b / divisor_out for b in widget["bytes_out"]]

                    max_value_in = max(scaled_bytes_in)
                    max_value_out = max(scaled_bytes_out)
                    min_value_in = min(scaled_bytes_in)
                    min_value_out = min(scaled_bytes_out)
                    margin_in = (max_value_in - min_value_in) * 0.1
                    margin_out = (max_value_out - min_value_out) * 0.1

                    ax_in.plot(
                        widget["timestamps"],
                        scaled_bytes_in,
                        label="Bytes In/s",
                        color="blue",
                    )
                    ax_in.set_title(f"Network Traffic In for {interface} ({unit_in}/s)")
                    ax_in.legend()
                    ax_in.set_ylim(min_value_in - margin_in, max_value_in + margin_in)
                    ax_in.set_xlim(left=max(0, system_time - 600))

                    ax_out.plot(
                        widget["timestamps"],
                        scaled_bytes_out,
                        label="Bytes Out/s",
                        color="red",
                    )
                    ax_out.set_title(
                        f"Network Traffic Out for {interface} ({unit_out}/s)"
                    )
                    ax_out.legend()
                    ax_out.set_ylim(
                        min_value_out - margin_out, max_value_out + margin_out
                    )
                    ax_out.set_xlim(left=max(0, system_time - 600))

                    formatted_times = [
                        datetime.datetime.fromtimestamp(t).strftime("%H:%M:%S")
                        for t in widget["timestamps"]
                    ]
                    ax_out.set_xticks(widget["timestamps"][::10])
                    ax_out.set_xticklabels(formatted_times[::10], rotation=45)
                    widget["fig"].canvas.draw()

    def determine_unit(self, max_value):
        if max_value >= 1024**3:
            return "GB", 1024**3
        elif max_value >= 1024**2:
            return "MB", 1024**2
        elif max_value >= 1024:
            return "KB", 1024
        else:
            return "B", 1

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

    def on_close_window(self):
        self.withdraw()

    def get_latest_metrics(self):
        return {
            "cpu": self.latest_cpu_metrics,
            "memory": self.latest_memory_metrics,
            "network": self.latest_network_metrics,
            "diskio": self.latest_diskio_metrics
        }