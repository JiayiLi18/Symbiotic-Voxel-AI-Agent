# core/tools/id_generator.py
"""
统一ID生成器 - 确保所有ID格式的一致性
"""

import random
import string
from datetime import datetime
from typing import Optional


class IDGenerator:
    """统一的ID生成器，遵循项目的ID命名规范"""
    
    @staticmethod
    def generate_session_id() -> str:
        """生成会话ID
        格式: sess_<timestamp>_<random>
        示例: sess_20241201_143052_a4b2
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
        return f"sess_{timestamp}_{random_suffix}"
    
    @staticmethod
    def generate_goal_id(session_id: str, sequence: int) -> str:
        """生成目标ID
        格式: goal_<session_suffix>_<sequence>
        示例: goal_a4b2_001
        """
        # 提取会话ID的随机后缀
        try:
            session_suffix = session_id.split('_')[-1]
        except (IndexError, AttributeError):
            session_suffix = "unkn"
        
        return f"goal_{session_suffix}_{sequence:03d}"
    
    @staticmethod
    def generate_plan_id(goal_id: str, sequence: int) -> str:
        """生成计划ID
        格式: plan_<goal_sequence>_<sequence>
        示例: plan_001_01
        """
        # 提取目标ID的序号
        try:
            goal_sequence = goal_id.split('_')[-1]
        except (IndexError, AttributeError):
            goal_sequence = "000"
        
        return f"plan_{goal_sequence}_{sequence:02d}"
    
    @staticmethod
    def generate_command_id(plan_id: str, sequence: int) -> str:
        """生成命令ID
        格式: cmd_<plan_id>_<sequence>
        示例: cmd_plan_001_01_001
        """
        return f"cmd_{plan_id}_{sequence:03d}"
    
    @staticmethod
    def extract_session_suffix(session_id: str) -> str:
        """从会话ID提取后缀，用于生成相关ID"""
        try:
            return session_id.split('_')[-1]
        except (IndexError, AttributeError):
            return "unkn"
    
    @staticmethod
    def extract_goal_sequence(goal_id: str) -> str:
        """从目标ID提取序号，用于生成相关ID"""
        try:
            return goal_id.split('_')[-1]
        except (IndexError, AttributeError):
            return "000"


# 便利函数，供外部直接使用
def new_session_id() -> str:
    """生成新的会话ID"""
    return IDGenerator.generate_session_id()


def new_goal_id(session_id: str, sequence: int = 1) -> str:
    """生成新的目标ID"""
    return IDGenerator.generate_goal_id(session_id, sequence)


def new_plan_id(goal_id: str, sequence: int = 1) -> str:
    """生成新的计划ID"""
    return IDGenerator.generate_plan_id(goal_id, sequence)


def new_command_id(plan_id: str, sequence: int = 1) -> str:
    """生成新的命令ID"""
    return IDGenerator.generate_command_id(plan_id, sequence)
