import tkinter as tk
from tkinter import messagebox
from detail_window import DetailWindow
import asyncio
class AddNodeWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Add New Node")
        self.geometry("300x300")
        self.resizable(False, False)

        self.name_label = tk.Label(self, text="Name")
        self.name_label.pack()
        self.name_entry = tk.Entry(self)
        self.name_entry.pack()

        self.host_label = tk.Label(self, text="Host")
        self.host_label.pack()
        self.host_entry = tk.Entry(self)
        self.host_entry.pack()

        self.user_label = tk.Label(self, text="User")
        self.user_label.pack()
        self.user_entry = tk.Entry(self)
        self.user_entry.pack()

        self.password_label = tk.Label(self, text="Password")
        self.password_label.pack()
        self.password_entry = tk.Entry(self, show="*")
        self.password_entry.pack()

        self.use_key_var = tk.BooleanVar()
        self.use_key_check = tk.Checkbutton(
            self,
            text="Use SSH Key",
            variable=self.use_key_var,
            command=self.toggle_key_entry,
        )
        self.use_key_check.pack()

        self.key_path_label = tk.Label(self, text="Key Path")
        self.key_path_label.pack()
        self.key_path_entry = tk.Entry(self)
        self.key_path_entry.pack()
        self.key_path_entry.config(state=tk.DISABLED)

        self.add_button = tk.Button(self, text="Add", command=self.add_node)
        self.add_button.pack()

    def toggle_key_entry(self):
        if self.use_key_var.get():
            self.key_path_entry.config(state=tk.NORMAL)
            self.password_entry.config(state=tk.DISABLED)
        else:
            self.key_path_entry.config(state=tk.DISABLED)
            self.password_entry.config(state=tk.NORMAL)

    def add_node(self):
        name = self.name_entry.get()
        host = self.host_entry.get()

        for node_info in self.parent.node_info_list:
            if node_info["name"] == name:
                messagebox.showerror("Error", "Node with the same name already exists")
                return
            if node_info["host"] == host:
                messagebox.showerror("Error", "Node with the same host already exists")
                return

        user = self.user_entry.get()
        password = self.password_entry.get()
        use_key = self.use_key_var.get()
        key_path = self.key_path_entry.get() if use_key else ""

        if not name or not host or not user or (not password and not use_key):
            messagebox.showerror("Error", "Please fill in all fields")
            return

        new_node_info = {
            "name": name,
            "host": host,
            "user": user,
            "password": password,
            "use_key": use_key,
            "key_path": key_path,
        }

        self.parent.node_info_list.append(new_node_info)
        asyncio.ensure_future(self.parent.add_node_card(new_node_info))
        self.parent.save_nodes()
        """ self.parent.detail_windows[new_node_info["name"]] = DetailWindow(
            self.parent, new_node_info
        ) """
        if hasattr(self.parent, "empty_label"):
            self.parent.empty_label.destroy()
        self.destroy()


class EditNodeWindow(tk.Toplevel):
    def __init__(self, parent, node_info, on_update):
        super().__init__(parent)
        self.app = parent
        self.node_info = node_info
        self.on_update = on_update
        self.title(f"Edit Node: {node_info['name']}")
        self.geometry("300x300")
        self.resizable(False, False)

        self.name_label = tk.Label(self, text="Name")
        self.name_label.pack()
        self.name_entry = tk.Entry(self)
        self.name_entry.pack()
        self.name_entry.insert(0, node_info["name"])

        self.host_label = tk.Label(self, text="Host")
        self.host_label.pack()
        self.host_entry = tk.Entry(self)
        self.host_entry.pack()
        self.host_entry.insert(0, node_info["host"])

        self.user_label = tk.Label(self, text="User")
        self.user_label.pack()
        self.user_entry = tk.Entry(self)
        self.user_entry.pack()
        self.user_entry.insert(0, node_info["user"])

        self.password_label = tk.Label(self, text="Password")
        self.password_label.pack()
        self.password_entry = tk.Entry(self, show="*")
        self.password_entry.pack()
        self.password_entry.insert(0, node_info["password"])

        self.use_key_var = tk.BooleanVar(value=node_info.get("use_key", False))
        self.use_key_check = tk.Checkbutton(
            self,
            text="Use SSH Key",
            variable=self.use_key_var,
            command=self.toggle_key_entry,
        )
        self.use_key_check.pack()

        self.key_path_label = tk.Label(self, text="Key Path")
        self.key_path_label.pack()
        self.key_path_entry = tk.Entry(self)
        self.key_path_entry.pack()
        self.key_path_entry.insert(0, node_info.get("key_path", ""))
        if not node_info.get("use_key", False):
            self.key_path_entry.config(state=tk.DISABLED)

        self.save_button = tk.Button(self, text="Save", command=self.save_changes)
        self.save_button.pack()

    def toggle_key_entry(self):
        if self.use_key_var.get():
            self.key_path_entry.config(state=tk.NORMAL)
            self.password_entry.config(state=tk.DISABLED)
        else:
            self.key_path_entry.config(state=tk.DISABLED)
            self.password_entry.config(state=tk.NORMAL)

    def save_changes(self):
        new_name = self.name_entry.get()
        new_host = self.host_entry.get()

        for node in self.app.node_info_list:
            if node == self.node_info:
                continue
            if node["name"] == new_name:
                messagebox.showerror("Error", "Node with the same name already exists")
                return
            if node["host"] == new_host:
                messagebox.showerror("Error", "Node with the same host already exists")
                return

        updated_info = {
            "name": new_name,
            "host": new_host,
            "user": self.user_entry.get(),
            "password": self.password_entry.get(),
            "use_key": self.use_key_var.get(),
            "key_path": self.key_path_entry.get(),
        }
        self.on_update(self.node_info, updated_info)
        self.destroy()
