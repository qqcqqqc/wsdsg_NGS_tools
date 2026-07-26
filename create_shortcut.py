import os
import sys

def create_shortcut():
    curr_dir = os.path.abspath(os.path.dirname(__file__))
    bat_path = os.path.join(curr_dir, "双击启动软件.bat")
    icon_path = os.path.join(curr_dir, "assets", "app_icon.ico")
    
    desktop_dir = os.path.join(os.path.expanduser("~"), "Desktop")
    if not os.path.exists(desktop_dir):
        desktop_dir = os.path.join(os.environ.get("USERPROFILE", "C:\\"), "Desktop")
        
    lnk_path = os.path.join(desktop_dir, "宇宙无敌NGS tool-cql定制版.lnk")
    vbs_path = os.path.join(curr_dir, "_temp_shortcut.vbs")
    
    vbs_content = f'''Set WshShell = CreateObject("WScript.Shell")
Set shortcut = WshShell.CreateShortcut("{lnk_path}")
shortcut.TargetPath = "{bat_path}"
shortcut.WorkingDirectory = "{curr_dir}"
shortcut.IconLocation = "{icon_path}"
shortcut.Save
'''
    try:
        with open(vbs_path, "w", encoding="gbk", errors="ignore") as f:
            f.write(vbs_content)
            
        os.system(f'cscript //NoLogo "{vbs_path}"')
        print("桌面快捷方式 [宇宙无敌NGS tool-cql定制版] 创建成功！")
        print(f"位置: {lnk_path}")
    except Exception as e:
        print(f"创建失败: {e}")
    finally:
        if os.path.exists(vbs_path):
            try:
                os.remove(vbs_path)
            except Exception:
                pass

if __name__ == "__main__":
    create_shortcut()
