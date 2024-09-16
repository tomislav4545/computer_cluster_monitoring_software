import asyncssh
import asyncio
import re


class SSHConnectionManager:
    def __init__(self):
        self.ssh_connections = {}
        self.lock = asyncio.Lock()

    async def get_ssh_connection(self, node_info, max_retries=1, delay=1):
        node_id = f"{node_info['host']}_{node_info['user']}"

        async with self.lock:
            if node_id not in self.ssh_connections:
                for attempt in range(max_retries):
                    try:
                        if node_info["use_key"]:
                            ssh_client = await asyncssh.connect(
                                node_info["host"],
                                username=node_info["user"],
                                client_keys=[node_info["key_path"]],
                                known_hosts=None,
                                connect_timeout=5.0
                            )
                        else:
                            ssh_client = await asyncssh.connect(
                                node_info["host"],
                                username=node_info["user"],
                                password=node_info["password"],
                                known_hosts=None,
                                connect_timeout=5.0
                            )
                        self.ssh_connections[node_id] = ssh_client
                        print(
                            f"Successfully connected to {node_info['name']} ({node_info['host']})"
                        )
                        return ssh_client, True
                    except Exception as e:
                        print(
                            f"Failed to connect to {node_info['name']} ({node_info['host']}): {e}"
                        )
                        if attempt < max_retries - 1:
                            print(f"Retrying in {delay} seconds...")
                            await asyncio.sleep(delay)
                        else:
                            print(f"Exceeded maximum retries for {node_info['name']} ({node_info['host']}). Giving up.")
                            return None, False

        return self.ssh_connections[node_id], True

    async def execute_command(self, ssh_client, command):
        result = await ssh_client.run(command)
        return result.stdout.strip()

    def parse_top_output(self, output):
        lines = output.split("\n")
        cpu_metrics = {}
        system_time = ""

        load_avg_pattern = re.compile(r"load average: ([\d\.]+), ([\d\.]+), ([\d\.]+)")
        time_pattern = re.compile(r"(\d{2}:\d{2}:\d{2})")

        for line in lines:
            time_match = time_pattern.search(line)
            if time_match:
                system_time = time_match.group(1)

            if "load average:" in line:
                load_match = load_avg_pattern.search(line)
                if load_match:
                    cpu_metrics.update(
                        {
                            "load_avg_1min": round(float(load_match.group(1)), 2),
                            "load_avg_5min": round(float(load_match.group(2)), 2),
                            "load_avg_15min": round(float(load_match.group(3)), 2),
                        }
                    )

            if line.startswith("%Cpu(s):"):
                parts = line.replace("%Cpu(s):", "").split(",")

                cpu_values = {}
                for part in parts:
                    value, metric = part.strip().split()
                    metric = metric.strip()
                    value = float(value.replace(",", "."))

                    if metric == "us":
                        cpu_values["cpu_user"] = round(value, 2)
                    elif metric == "sy":
                        cpu_values["cpu_system"] = round(value, 2)
                    elif metric == "ni":
                        cpu_values["cpu_nice"] = round(value, 2)
                    elif metric == "id":
                        cpu_values["cpu_idle"] = round(value, 2)
                    elif metric == "wa":
                        cpu_values["cpu_iowait"] = round(value, 2)
                    elif metric == "hi":
                        cpu_values["cpu_irq"] = round(value, 2)
                    elif metric == "si":
                        cpu_values["cpu_softirq"] = round(value, 2)
                    elif metric == "st":
                        cpu_values["cpu_steal"] = round(value, 2)

                cpu_values["cpu_load"] = round(100.0 - cpu_values["cpu_idle"], 2)
                cpu_metrics.update(cpu_values)
                break

        return system_time, cpu_metrics

    def parse_free_output(self, output):
        lines = output.split("\n")
        system_time = lines[0]
        memory_metrics = {}
        swap_metrics = {}

        memory_pattern = re.compile(
            r"Mem:\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)"
        )
        swap_pattern = re.compile(r"Swap:\s+(\d+)\s+(\d+)\s+(\d+)")

        for line in lines:
            memory_match = memory_pattern.search(line)
            if memory_match:
                total_mem = int(memory_match.group(1))
                used_mem = int(memory_match.group(2))
                free_mem = int(memory_match.group(3))

                memory_metrics = {
                    "total": round(total_mem / 1024, 2),
                    "used": round(used_mem / 1024, 2),
                    "free": round(free_mem / 1024, 2),
                    "shared": round(int(memory_match.group(4)) / 1024, 2),
                    "buff_cache": round(int(memory_match.group(5)) / 1024, 2),
                    "available": round(int(memory_match.group(6)) / 1024, 2),
                    "used_percent": round((used_mem / total_mem) * 100, 2),
                }

            swap_match = swap_pattern.search(line)
            if swap_match:
                total_mem = int(swap_match.group(1))
                used_mem = int(swap_match.group(2))
                free_mem = int(swap_match.group(3))
                swap_metrics = {
                    "total": round(int(swap_match.group(1)) / 1024, 2),
                    "used": round(int(swap_match.group(2)) / 1024, 2),
                    "free": round(int(swap_match.group(3)) / 1024, 2),
                    "used_percent": round((used_mem / total_mem) * 100, 2),
                }

        return system_time, memory_metrics, swap_metrics

    def parse_node_card_output(self, output):
        lines = output.split("\n")
        total_memory = None
        used_memory = None
        cpu_usage = None

        memory_pattern = re.compile(r"Mem:\s+(\d+)\s+(\d+)\s+\d+\s+\d+\s+(\d+)")

        for line in lines:
            memory_match = memory_pattern.search(line)
            if memory_match:
                total_memory = int(memory_match.group(1))
                used_memory = int(memory_match.group(2))

            if line.startswith("%Cpu(s):"):
                parts = line.replace("%Cpu(s):", "").split(",")
                cpu_values = {}
                for part in parts:
                    value, metric = part.strip().split()
                    metric = metric.strip()
                    value = float(value.replace(",", "."))
                    if metric == "us":
                        cpu_values["cpu_user"] = round(value, 2)
                    elif metric == "sy":
                        cpu_values["cpu_system"] = round(value, 2)
                    elif metric == "ni":
                        cpu_values["cpu_nice"] = round(value, 2)
                    elif metric == "id":
                        cpu_values["cpu_idle"] = round(value, 2)
                cpu_values["cpu_load"] = round(100.0 - cpu_values["cpu_idle"], 2)
                cpu_usage = cpu_values["cpu_load"]
                break

        memory_usage = (
            round((used_memory / total_memory) * 100, 2)
            if total_memory and used_memory
            else None
        )

        return cpu_usage, memory_usage

    async def collect_nodecard_metrics(self, node_info):
        ssh_client, success = await self.get_ssh_connection(node_info)
        if not success:
            return None, None
        output = await self.execute_command(ssh_client, "free && top -bn1")
        return self.parse_node_card_output(output)

    async def collect_cpu_metrics(self, node_info):
        ssh_client, success = await self.get_ssh_connection(node_info)
        if not success:
            return None, None
        output = await self.execute_command(ssh_client, "top -bn1")
        return self.parse_top_output(output)

    async def collect_memory_metrics(self, node_info):
        ssh_client, success = await self.get_ssh_connection(node_info)
        if not success:
            return None, None, None
        output = await self.execute_command(ssh_client, "date '+%T' && free")
        return self.parse_free_output(output)

    def parse_df_output(self, output):
        lines = output.split("\n")
        system_time = lines[0]
        headers = lines[1].split()
        volumes = []

        for line in lines[1:]:
            if line:
                parts = line.split()
                filesystem = parts[0]
                size = parts[1]
                used = parts[2]
                available = parts[3]
                use_percent = parts[4]
                mounted_on = parts[5]
                volumes.append(
                    {
                        "filesystem": filesystem,
                        "size": size,
                        "used": used,
                        "available": available,
                        "use_percent": use_percent,
                        "mounted_on": mounted_on,
                    }
                )

        return system_time, volumes

    def filter_volumes(self, volumes):
        patterns = [r"/dev/"]
        filtered_volumes = []
        for volume in volumes:
            for pattern in patterns:
                if re.search(pattern, volume["filesystem"]):
                    filtered_volumes.append(volume)
                    break
        return filtered_volumes

    async def collect_disk_metrics(self, node_info):
        ssh_client, success = await self.get_ssh_connection(node_info)
        if not success:
            return None, None
        output = await self.execute_command(ssh_client, "date '+%T' && df -h")
        system_time, volumes_info = self.parse_df_output(output)
        filtered_volumes_info = self.filter_volumes(volumes_info)
        return system_time, filtered_volumes_info

    def parse_network_stats(self, output):
        lines = output.split("\n")
        net_data = {}
        for line in lines[2:]:
            if line:
                parts = line.split()
                if len(parts) < 17:
                    continue
                interface = parts[0].strip(":")
                bytes_in = int(parts[1])
                bytes_out = int(parts[9])
                net_data[interface] = {"bytes_in": bytes_in, "bytes_out": bytes_out}
        return net_data

    def calculate_diff(self, old_stats, new_stats, interval):
        diff_stats = {}
        for interface in new_stats:
            if interface in old_stats:
                bytes_in_diff = (
                    new_stats[interface]["bytes_in"] - old_stats[interface]["bytes_in"]
                ) / interval
                bytes_out_diff = (
                    new_stats[interface]["bytes_out"]
                    - old_stats[interface]["bytes_out"]
                ) / interval
                diff_stats[interface] = {
                    "bytes_in/s": bytes_in_diff,
                    "bytes_out/s": bytes_out_diff,
                }
        return diff_stats

    def convert_units(self, value, unit="B/s"):
        thresholds = {
            "B/s": 1024,
            "KB/s": 1024,
            "MB/s": 1024,
            "GB/s": 1024,
        }
        units = ["B/s", "KB/s", "MB/s", "GB/s"]
        index = 0
        while value >= thresholds[unit] and index < len(units) - 1:
            value /= 1024
            index += 1
            unit = units[index]
        return f"{value:.2f} {unit}"

    async def collect_network_metrics(self, node_info):
        ssh_client, success = await self.get_ssh_connection(node_info)
        if not success:
            return None, None
        interval = 1
        command = "cat /proc/net/dev"

        old_output = await self.execute_command(ssh_client, command)
        old_stats = self.parse_network_stats(old_output)

        await asyncio.sleep(interval)

        new_output = await self.execute_command(ssh_client, command)
        new_stats = self.parse_network_stats(new_output)
        system_time = await self.execute_command(ssh_client, "date '+%T'")

        diff_stats = self.calculate_diff(old_stats, new_stats, interval)

        for interface in diff_stats:
            diff_stats[interface]["bytes_in/s"] = self.convert_units(
                diff_stats[interface]["bytes_in/s"]
            )
            diff_stats[interface]["bytes_out/s"] = self.convert_units(
                diff_stats[interface]["bytes_out/s"]
            )

        return system_time, diff_stats

    def parse_diskio_stats(self, output):
        lines = output.split("\n")
        disk_data = {}
        base_drive_pattern = re.compile(r"^(sd[a-z]+|mmcblk[0-9]+)$")
        for line in lines:
            if line:
                parts = line.split()
                if len(parts) < 14:
                    continue
                device = parts[2]
                if base_drive_pattern.match(device):
                    reads_completed = int(parts[3])
                    reads_merged = int(parts[4])
                    sectors_read = int(parts[5])
                    time_spent_reading = int(parts[6])
                    writes_completed = int(parts[7])
                    writes_merged = int(parts[8])
                    sectors_written = int(parts[9])
                    time_spent_writing = int(parts[10])
                    io_in_progress = int(parts[11])
                    time_spent_doing_io = int(parts[12])
                    weighted_time_spent_doing_io = int(parts[13])
                    disk_data[device] = {
                        "reads_completed": reads_completed,
                        "reads_merged": reads_merged,
                        "sectors_read": sectors_read,
                        "time_spent_reading": time_spent_reading,
                        "writes_completed": writes_completed,
                        "writes_merged": writes_merged,
                        "sectors_written": sectors_written,
                        "time_spent_writing": time_spent_writing,
                        "io_in_progress": io_in_progress,
                        "time_spent_doing_io": time_spent_doing_io,
                        "weighted_time_spent_doing_io": weighted_time_spent_doing_io,
                    }
        return disk_data

    def calculate_iodiff(self, old_stats, new_stats, interval):
        diff_stats = {}
        for device in new_stats:
            if device in old_stats:
                reads_completed_diff = (
                    new_stats[device]["reads_completed"]
                    - old_stats[device]["reads_completed"]
                ) / interval
                writes_completed_diff = (
                    new_stats[device]["writes_completed"]
                    - old_stats[device]["writes_completed"]
                ) / interval
                sectors_read_diff = (
                    new_stats[device]["sectors_read"]
                    - old_stats[device]["sectors_read"]
                ) / interval
                sectors_written_diff = (
                    new_stats[device]["sectors_written"]
                    - old_stats[device]["sectors_written"]
                ) / interval
                read_bytes_per_sec = sectors_read_diff * 512
                write_bytes_per_sec = sectors_written_diff * 512
                io_ops_per_sec = reads_completed_diff + writes_completed_diff
                diff_stats[device] = {
                    "reads/s": reads_completed_diff,
                    "writes/s": writes_completed_diff,
                    "read_bytes/s": read_bytes_per_sec,
                    "write_bytes/s": write_bytes_per_sec,
                    "io_ops/s": io_ops_per_sec,
                }
        return diff_stats

    def convert_iounits(self, value, unit="B/s"):
        thresholds = {
            "B/s": 1024,
            "KB/s": 1024,
            "MB/s": 1024,
            "GB/s": 1024,
        }
        units = ["B/s", "KB/s", "MB/s", "GB/s"]
        index = 0
        while value >= thresholds[unit] and index < len(units) - 1:
            value /= 1024
            index += 1
            unit = units[index]
        return f"{value:.2f} {unit}"

    async def collect_diskio_metrics(self, node_info):
        ssh_client, success = await self.get_ssh_connection(node_info)
        if not success:
            return None, None
        interval = 1

        command = "cat /proc/diskstats"

        old_output = await self.execute_command(ssh_client, command)
        old_stats = self.parse_diskio_stats(old_output)

        await asyncio.sleep(interval)

        new_output = await self.execute_command(ssh_client, command)
        new_stats = self.parse_diskio_stats(new_output)
        system_time = await self.execute_command(ssh_client, "date '+%T'")

        diff_stats = self.calculate_iodiff(old_stats, new_stats, interval)

        for device in diff_stats:
            diff_stats[device]["read_bytes/s"] = self.convert_iounits(
                diff_stats[device]["read_bytes/s"]
            )
            diff_stats[device]["write_bytes/s"] = self.convert_iounits(
                diff_stats[device]["write_bytes/s"]
            )

        return system_time, diff_stats

    async def collect_system_info(self, node_info):
        ssh_client, success = await self.get_ssh_connection(node_info)
        if not success:
            return None
        output = await self.execute_command(
            ssh_client,
            "uname -sr && uname -m && lscpu | sed -n 's/Model name:[[:space:]]*//p' && nproc && grep -oP 'MemTotal:\\s*\\K\\d+' /proc/meminfo | awk '{printf \"%.2f GB\\n\", $1 / 1024 / 1024}' && hostname && df -BG --total | awk '/total/ {print $2}' && grep 'PRETTY_NAME' /etc/*-release | cut -d '=' -f 2 | tr -d '\"'",
        )
        system_info = self.parse_system_info(output)
        return system_info

    def parse_system_info(self, output):
        lines = output.split("\n")
        parsed_output = {}

        parsed_output["kernel"] = lines[0]
        parsed_output["architecture"] = lines[1]
        parsed_output["processor_name"] = lines[2]
        parsed_output["number_of_cores"] = int(lines[3])
        parsed_output["total_ram"] = lines[4]
        parsed_output["hostname"] = lines[5]
        parsed_output["total_disk_space"] = lines[6]
        parsed_output["linux_distribution"] = lines[7]

        return parsed_output

    async def close_all_connections(self):
        async with self.lock:
            for ssh_client in self.ssh_connections.values():
                ssh_client.close()
            self.ssh_connections.clear()

    async def close_ssh_connection(self, node_info):
        node_id = f"{node_info['host']}_{node_info['user']}"

        async with self.lock:
            if node_id in self.ssh_connections:
                self.ssh_connections[node_id].close()
                del self.ssh_connections[node_id]
                print(f"Connection to {node_id} closed.")
            else:
                print(f"No active connection found for {node_id}.")


ssh_manager = SSHConnectionManager()

async def get_ssh_connection(node_info):
    return await ssh_manager.get_ssh_connection(node_info)

async def collect_nodecard_metrics(node_info):
    return await ssh_manager.collect_nodecard_metrics(node_info)

async def collect_cpu_metrics(node_info):
    return await ssh_manager.collect_cpu_metrics(node_info)

async def collect_memory_metrics(node_info):
    return await ssh_manager.collect_memory_metrics(node_info)

async def collect_disk_metrics(node_info):
    return await ssh_manager.collect_disk_metrics(node_info)

async def collect_network_metrics(node_info):
    return await ssh_manager.collect_network_metrics(node_info)

async def collect_diskio_metrics(node_info):
    return await ssh_manager.collect_diskio_metrics(node_info)

async def collect_system_info(node_info):
    return await ssh_manager.collect_system_info(node_info)

async def close_ssh_connection(node_info):
    await ssh_manager.close_ssh_connection(node_info)
