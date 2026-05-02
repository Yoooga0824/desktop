"""
Mode 3 (终端云Agent) 审批请求处理

功能:
1. 从终端历史中识别"审批请求 #xxxxx"格式的消息
2. 提取请求ID
3. 生成 /approve 命令

审批请求格式示例:
  审批请求 #req_abc123def456
  
生成的命令示例:
  Key2 (同意): /approve req_abc123def456 allow-once
  Key3 (拒绝): /approve req_abc123def456 deny
"""

import re
from typing import Optional
from pathlib import Path
import subprocess


class TerminalAgentRequestParser:
    """终端审批请求解析器"""
    
    # 审批请求格式: "审批请求 #xxxxxx"
    REQUEST_PATTERN = re.compile(r"审批请求\s+#([a-zA-Z0-9_]+)")
    
    @staticmethod
    def extract_request_id_from_text(text: str) -> Optional[str]:
        """
        从文本中提取请求ID
        
        Args:
            text: 包含审批请求的文本
            
        Returns:
            请求ID (不含#) 或 None 如果没有找到
            
        示例:
            extract_request_id_from_text("审批请求 #req123")
            # 返回: "req123"
        """
        match = TerminalAgentRequestParser.REQUEST_PATTERN.search(text)
        return match.group(1) if match else None
    
    @staticmethod
    def get_recent_approval_request() -> Optional[str]:
        """
        从系统获取最近的审批请求ID
        
        策略: 尝试按优先级获取:
        1. PowerShell 历史文件 (Windows PowerShell / PowerShell 7+)
        2. CMD history (如果可用)
        
        Returns:
            请求ID 或 None
        """
        # 尝试读取 PowerShell 历史
        powershell_history = TerminalAgentRequestParser._read_powershell_history()
        if powershell_history:
            request_id = TerminalAgentRequestParser.extract_request_id_from_text(powershell_history)
            if request_id:
                return request_id
        
        return None
    
    @staticmethod
    def _read_powershell_history() -> Optional[str]:
        """
        读取 PowerShell 历史文件 (PSReadLine)
        
        历史文件位置:
        - Windows PowerShell: %APPDATA%\\Microsoft\\Windows\\PowerShell\\PSReadline\\ConsoleHost_history.txt
        - PowerShell 7+: %APPDATA%\\Microsoft\\PowerShell\\PSReadline\\ConsoleHost_history.txt
        
        Returns:
            历史文件内容 (最近100行) 或 None
        """
        try:
            import os
            appdata = os.getenv("APPDATA")
            if not appdata:
                return None
            
            # 尝试两个位置
            possible_paths = [
                Path(appdata) / "Microsoft" / "Windows" / "PowerShell" / "PSReadline" / "ConsoleHost_history.txt",
                Path(appdata) / "Microsoft" / "PowerShell" / "PSReadline" / "ConsoleHost_history.txt",
            ]
            
            for history_file in possible_paths:
                if history_file.exists():
                    try:
                        # 读取最后100行
                        with open(history_file, "r", encoding="utf-8", errors="ignore") as f:
                            lines = f.readlines()
                            recent = "".join(lines[-100:])
                            return recent if recent else None
                    except Exception:
                        continue
            
            return None
        except Exception:
            return None


class TerminalAgentCommandGenerator:
    """终端审批命令生成器"""
    
    COMMAND_TEMPLATE = "/approve {request_id} {action}"
    
    # 操作类型映射: 0=allow-once, 1=deny
    ACTION_MAP = {
        0: "allow-once",
        1: "deny",
    }
    
    @staticmethod
    def generate_command(request_id: str, action_type: int) -> Optional[str]:
        """
        生成审批命令
        
        Args:
            request_id: 审批请求ID (不含#)
            action_type: 0=同意(allow-once), 1=拒绝(deny)
            
        Returns:
            完整的审批命令字符串
            
        示例:
            generate_command("req123", 0)
            # 返回: "/approve req123 allow-once"
            
            generate_command("req123", 1)
            # 返回: "/approve req123 deny"
        """
        if action_type not in TerminalAgentCommandGenerator.ACTION_MAP:
            return None
        
        action = TerminalAgentCommandGenerator.ACTION_MAP[action_type]
        return TerminalAgentCommandGenerator.COMMAND_TEMPLATE.format(
            request_id=request_id,
            action=action
        )
    
    @staticmethod
    def get_approval_command(action_type: int) -> Optional[str]:
        """
        一步式获取完整审批命令
        
        步骤:
        1. 从终端获取最近的审批请求ID
        2. 生成相应的审批命令
        
        Args:
            action_type: 0=同意, 1=拒绝
            
        Returns:
            完整的审批命令 或 None (如果没有找到请求ID)
        """
        request_id = TerminalAgentRequestParser.get_recent_approval_request()
        if not request_id:
            return None
        
        return TerminalAgentCommandGenerator.generate_command(request_id, action_type)
