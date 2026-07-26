import subprocess
import shutil
import sys
from typing import Dict, Any
from core.platform_runner import is_windows, is_macos, is_linux, global_runner

def check_environment() -> Dict[str, Any]:
    """
    Check availability of core bioinfo tools (cutadapt, CRISPResso2) in the active environment/WSL.
    """
    status = {
        'os': sys.platform,
        'is_windows': is_windows(),
        'wsl_available': False,
        'cutadapt_installed': False,
        'crispresso_installed': False,
        'messages': []
    }
    
    runner = global_runner
    
    if is_windows():
        try:
            res = subprocess.run(["wsl", "--list", "--quiet"], capture_output=True, text=True, errors='ignore')
            if res.returncode == 0:
                status['wsl_available'] = True
                status['messages'].append("[OK] WSL2 运行环境已就绪")
            else:
                status['messages'].append("[X] 未能检测到 WSL2，请先安装 WSL2 (在 PowerShell 执行: wsl --install)")
        except Exception as e:
            status['messages'].append(f"[X] WSL 检测失败: {e}")
    else:
        status['wsl_available'] = True
        status['messages'].append("[OK] 原生 Linux/macOS 环境")

    # Check cutadapt
    code, out = runner.run_cmd(["cutadapt", "--version"])
    if code == 0:
        status['cutadapt_installed'] = True
        status['messages'].append(f"[OK] cutadapt 已就绪: {out.strip()}")
    else:
        status['messages'].append("[X] 缺少 cutadapt，请运行: conda install -c bioconda cutadapt")

    # Check CRISPResso2
    code, out = runner.run_cmd(["CRISPResso", "--version"])
    if code != 0:
        code, out = runner.run_cmd(["CRISPResso2", "--version"])
        
    if code == 0:
        status['crispresso_installed'] = True
        status['messages'].append(f"[OK] CRISPResso2 已就绪: {out.strip()}")
    else:
        status['messages'].append("[X] 缺少 CRISPResso2，请运行: conda install -c bioconda crispresso2")

    return status

if __name__ == '__main__':
    res = check_environment()
    for m in res['messages']:
        print(m)
