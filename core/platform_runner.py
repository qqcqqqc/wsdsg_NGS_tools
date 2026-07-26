import os
import sys
import subprocess
import shutil
import platform
import re
from typing import Callable, Optional, Tuple, List, Union

def is_windows() -> bool:
    return sys.platform.startswith('win') or os.name == 'nt'

def is_macos() -> bool:
    return sys.platform == 'darwin'

def is_linux() -> bool:
    return sys.platform.startswith('linux')

def win_to_wsl_path(path_str: str) -> str:
    r"""
    Convert Windows path or WSL UNC network path (e.g. \\wsl.localhost\Ubuntu\home\user\...)
    or file:C:\... to WSL internal path (/home/user/... or /mnt/c/Users/xxx).
    """
    if not path_str:
        return ""
    
    path_str = str(path_str).strip()
    prefix = ""
    if path_str.startswith("file:"):
        prefix = "file:"
        path_str = path_str[5:]
        
    path_str = path_str.replace('\\', '/')
    
    unc_match = re.match(r'^//wsl(?:\.localhost|\$)/[^/]+/(.*)', path_str, re.IGNORECASE)
    if unc_match:
        rel_unix_path = unc_match.group(1)
        return f"{prefix}/{rel_unix_path}"
        
    if path_str.startswith('/'):
        return f"{prefix}{path_str}"
        
    match = re.match(r'^([a-zA-Z]):/(.*)', path_str)
    if match:
        drive_letter = match.group(1).lower()
        rest_path = match.group(2)
        return f"{prefix}/mnt/{drive_letter}/{rest_path}"
        
    return f"{prefix}{path_str}"

def wsl_to_win_path(wsl_path: str) -> str:
    r"""
    Convert WSL path (/mnt/c/Users/xxx or /home/xxx) back to Windows path.
    """
    if not wsl_path:
        return ""
        
    wsl_path = str(wsl_path).strip()
    prefix = ""
    if wsl_path.startswith("file:"):
        prefix = "file:"
        wsl_path = wsl_path[5:]
        
    match = re.match(r'^/mnt/([a-zA-Z])/(.*)', wsl_path)
    if match:
        drive_letter = match.group(1).upper()
        rest_path = match.group(2).replace('/', '\\')
        return f"{prefix}{drive_letter}:\\{rest_path}"
        
    converted = wsl_path.replace('/', '\\')
    return f"{prefix}{converted}"

class PlatformRunner:
    """
    Handles cross-platform command execution (direct execution on macOS/Linux,
    and wsl -e execution on Windows) with real-time process control.
    """
    def __init__(self, use_wsl: Optional[bool] = None):
        if use_wsl is None:
            self.use_wsl = is_windows()
        else:
            self.use_wsl = use_wsl
        self.current_process: Optional[subprocess.Popen] = None

    def format_command(self, cmd_args: List[str]) -> List[str]:
        """
        Format a command list for the current operating system.
        """
        if self.use_wsl:
            escaped_args = []
            for arg in cmd_args:
                if ':\\' in arg or ':/' in arg or 'wsl.localhost' in arg or 'wsl$' in arg or arg.startswith("file:") or (os.path.exists(arg) and not arg.startswith("-")):
                    abs_arg = os.path.abspath(arg) if os.path.exists(arg) else arg
                    arg = win_to_wsl_path(abs_arg)
                escaped_args.append(arg)
            
            raw_cmd = " ".join(f"'{a}'" if (" " in a or "$" in a or "*" in a) else a for a in escaped_args)
            
            wsl_bash_script = (
                "source ~/.bashrc 2>/dev/null; "
                "if ! command -v cutadapt >/dev/null 2>&1 || ! command -v CRISPResso >/dev/null 2>&1; then "
                "  for e in ngs crispresso2 crispresso bio base; do "
                "    conda activate \"$e\" 2>/dev/null && break; "
                "  done; "
                "fi; "
                "export PATH=$HOME/miniconda3/envs/ngs/bin:$HOME/miniconda3/bin:$HOME/.local/bin:$PATH; "
                f"{raw_cmd}"
            )
            return ["wsl", "-e", "bash", "-l", "-c", wsl_bash_script]
        else:
            return cmd_args

    def run_cmd(self, cmd_args: List[str], log_callback: Optional[Callable[[str], None]] = None) -> Tuple[int, str]:
        """
        Execute command synchronously or with real-time log output via log_callback.
        Tracks active subprocess for instant cancellation.
        """
        final_cmd = self.format_command(cmd_args)
        
        if log_callback:
            log_callback(f"[EXEC] {' '.join(final_cmd)}\n")

        try:
            self.current_process = subprocess.Popen(
                final_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                errors='replace',
                bufsize=1
            )
            
            output_lines = []
            if self.current_process.stdout:
                for line in self.current_process.stdout:
                    output_lines.append(line)
                    if log_callback:
                        log_callback(line)
            
            self.current_process.wait()
            ret_code = self.current_process.returncode
            self.current_process = None
            return ret_code, "".join(output_lines)
            
        except Exception as e:
            err_msg = f"[ERROR] Failed to run command {final_cmd}: {str(e)}\n"
            if log_callback:
                log_callback(err_msg)
            self.current_process = None
            return -1, err_msg

    def kill_current_process(self):
        """Forcibly terminate currently running subprocess and all its WSL/Linux child processes immediately."""
        proc = self.current_process
        if proc is not None:
            try:
                if is_windows():
                    # 1. Kill the Windows wsl.exe process tree
                    try:
                        subprocess.call(['taskkill', '/F', '/T', '/PID', str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    except Exception:
                        pass

                    # 2. Issue forceful Linux pkill inside WSL for all cutadapt, CRISPResso, fastp, pigz processes
                    try:
                        kill_script = "pkill -9 -f cutadapt 2>/dev/null; pkill -9 -f CRISPResso 2>/dev/null; pkill -9 -f fastp 2>/dev/null; pkill -9 -f pigz 2>/dev/null; pkill -9 -f python 2>/dev/null"
                        subprocess.call(['wsl', '-e', 'bash', '-c', kill_script], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    except Exception:
                        pass
                else:
                    try:
                        proc.kill()
                    except Exception:
                        pass
            except Exception as e:
                print(f"Error killing process: {e}")
            finally:
                self.current_process = None

global_runner = PlatformRunner()
