import argparse
import zipfile
import os
import sys
import io
import csv
import datetime
import tkinter as tk
from tkinter import scrolledtext, messagebox
import xml.etree.ElementTree as ET


class VShell:
    def __init__(self, zip_path, config_path=None, log_file='action_log.csv'):
        self.zip_path = zip_path
        self.current_directory = '/'
        self.filesystem = {}
        self.permissions = {}
        self.log_file = log_file

        # Открываем zip-файл и читаем его содержимое
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            for zip_info in zip_ref.infolist():
                if not zip_info.is_dir():
                    self.filesystem[zip_info.filename] = zip_ref.read(zip_info.filename).decode('utf-8')
                    self.permissions[zip_info.filename] = 'rw'

        # Загружаем конфигурацию из XML, если она предоставлена
        if config_path:
            self.load_config(config_path)

    def load_config(self, config_path):
        tree = ET.parse(config_path)
        root = tree.getroot()
        for file in root.find('filesystem').findall('file'):
            name = file.get('name')
            content = file.text.strip() if file.text else ''
            permissions = file.get('permissions', 'rw')
            self.filesystem[name] = content
            self.permissions[name] = permissions

        for directory in root.find('filesystem').findall('directory'):
            name = directory.get('name')
            self.filesystem[name + '/'] = ''

    def log_action(self, action, details):
        with open(self.log_file, mode='a', newline='') as log:
            writer = csv.writer(log)
            writer.writerow([datetime.datetime.now().isoformat(), action, details])

    def pwd(self):
        return self.current_directory

    def ls(self):
        path = self._abs_path(self.current_directory)
        return [name[len(path):] for name in self.filesystem if name.startswith(path) and len(name) > len(path)]

    def cd(self, path):
        new_path = self._abs_path(path)
        if any(name.startswith(new_path) for name in self.filesystem):
            self.current_directory = new_path
        else:
            raise FileNotFoundError(f"Directory {path} not found.")

    def cat(self, filename):
        file_path = self._abs_path(filename)
        if file_path in self.filesystem:
            return self.filesystem[file_path]
        else:
            raise FileNotFoundError(f"File {filename} not found.")

    def mkdir(self, directory):
        new_dir = self._abs_path(directory) + "/"
        if not any(name.startswith(new_dir) for name in self.filesystem):
            self.filesystem[new_dir] = ''
            self._write_to_zip()
            return f"Directory {directory} created."
        else:
            return f"Directory {directory} already exists."

    def nano(self, filename, content):
        file_path = self._abs_path(filename)
        if file_path not in self.filesystem:
            self.filesystem[file_path] = content
            self.permissions[file_path] = 'rw'
            self._write_to_zip()
            return f"File {filename} created."
        else:
            return f"File {filename} already exists."

    def rm(self, filename):
        file_path = self._abs_path(filename)
        if file_path in self.filesystem:
            del self.filesystem[file_path]
            del self.permissions[file_path]
            self._write_to_zip()
            return f"File {filename} removed."
        else:
            raise FileNotFoundError(f"File {filename} not found.")

    def chmod(self, filename, permissions):
        file_path = self._abs_path(filename)
        if file_path in self.filesystem:
            self.permissions[file_path] = permissions
            return f"Permissions for {filename} set to {permissions}."
        else:
            raise FileNotFoundError(f"File {filename} not found.")

    def _write_to_zip(self):
        with zipfile.ZipFile(self.zip_path, 'w') as zip_ref:
            for file_name, content in self.filesystem.items():
                zip_ref.writestr(file_name, content)

    def _abs_path(self, path):
        if path.startswith('/'):
            return path.lstrip('/')
        return os.path.join(self.current_directory, path).lstrip('/')


class VShellGUI:
    def __init__(self, master, zip_path, config_path):
        self.master = master
        self.master.title("Virtual Shell Emulator")
        self.shell = VShell(zip_path, config_path)

        self.text_area = scrolledtext.ScrolledText(master, wrap=tk.WORD, width=80, height=20)
        self.text_area.pack(padx=10, pady=10)

        self.entry = tk.Entry(master, width=80)
        self.entry.pack(padx=10, pady=5)
        self.entry.bind('<Return>', self.execute_command)

        self.status_label = tk.Label(master, text="")
        self.status_label.pack(pady=5)

    def execute_command(self, event):
        command = self.entry.get()
        self.entry.delete(0, tk.END)
        try:
            parts = command.split()
            cmd = parts[0]
            args = parts[1:]

            if cmd == "pwd":
                result = self.shell.pwd()
                self.text_area.insert(tk.END, f"{result}\n")
                self.shell.log_action('pwd', result)
            elif cmd == "ls":
                result = self.shell.ls()
                self.text_area.insert(tk.END, '\n'.join(result) + "\n")
                self.shell.log_action('ls', ', '.join(result))
            elif cmd == "cd":
                self.shell.cd(args[0])
                self.shell.log_action('cd', args[0])
                self.text_area.insert(tk.END, f"Changed directory to {args[0]}\n")
            elif cmd == "cat":
                result = self.shell.cat(args[0])
                self.text_area.insert(tk.END, f"{result}\n")
                self.shell.log_action('cat', args[0])
            elif cmd == "mkdir":
                result = self.shell.mkdir(args[0])
                self.text_area.insert(tk.END, f"{result}\n")
                self.shell.log_action('mkdir', args[0])
            elif cmd == "nano":
                if len(args) < 2:
                    messagebox.showinfo("Usage", "Usage: nano <filename> <content>")
                else:
                    filename = args[0]
                    content = ' '.join(args[1:])
                    result = self.shell.nano(filename, content)
                    self.text_area.insert(tk.END, f"{result}\n")
                    self.shell.log_action('nano', f'{filename}: {content}')
            elif cmd == "rm":
                result = self.shell.rm(args[0])
                self.text_area.insert(tk.END, f"{result}\n")
                self.shell.log_action('rm', args[0])
            elif cmd == "chmod":
                self.shell.chmod(args[0], args[1])
                self.shell.log_action('chmod', f'{args[0]}: {args[1]}')
                self.text_area.insert(tk.END, f"Permissions for {args[0]} set to {args[1]}.\n")
            elif cmd == "exit":
                self.shell.log_action('exit', '')
                self.master.quit()
            else:
                self.text_area.insert(tk.END, f"Command {cmd} not found.\n")
                self.shell.log_action('error', f'Command not found: {cmd}')
        except Exception as e:
            self.text_area.insert(tk.END, f'Error: {e}\n')
            self.shell.log_action('error', str(e))


def main():
    parser = argparse.ArgumentParser(description='Virtual Shell Emulator')
    parser.add_argument('zip_file', help='Path to the zip file representing the filesystem.')
    parser.add_argument('--script', help='File with commands to execute.')
    parser.add_argument('--config', help='Path to the XML configuration file.')
    args = parser.parse_args()

    root = tk.Tk()
    gui = VShellGUI(root, args.zip_file, args.config)
    root.mainloop()


if __name__ == "__main__":
    main()
