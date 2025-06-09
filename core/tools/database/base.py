# core/tools/database/base.py
from abc import ABC, abstractmethod
from typing import Dict, Optional
from datetime import datetime
import os
import json

class DatabaseInterface(ABC):
    """数据库基础接口"""
    @abstractmethod
    def load(self) -> Dict:
        """加载数据库"""
        pass

    @abstractmethod
    def save(self, data: Dict) -> None:
        """保存数据库"""
        pass

    @abstractmethod
    def get_summary(self) -> str:
        """获取数据库摘要"""
        pass

class JSONDatabase(DatabaseInterface):
    """JSON文件数据库实现"""
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._cache: Optional[Dict] = None
        self._last_read_time = 0

    def _should_reload(self) -> bool:
        """检查是否需要重新加载数据库"""
        if not self._cache or not self._last_read_time:
            return True
        try:
            mtime = os.path.getmtime(self.db_path)
            return mtime > self._last_read_time
        except OSError:
            return True

    def load(self) -> Dict:
        """加载数据库"""
        try:
            if self._should_reload():
                with open(self.db_path, 'r', encoding='utf-8') as f:
                    self._cache = json.load(f)
                self._last_read_time = os.path.getmtime(self.db_path)
            return self._cache
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Warning: Failed to load database: {e}")
            return {}

    def save(self, data: Dict) -> None:
        """保存数据库"""
        try:
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            with open(self.db_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
            self._cache = data
            self._last_read_time = os.path.getmtime(self.db_path)
        except Exception as e:
            raise Exception(f"Failed to save database: {e}")

    def get_summary(self) -> str:
        """获取数据库摘要"""
        data = self.load()
        return f"Database at {self.db_path}\nLast updated: {datetime.fromtimestamp(self._last_read_time)}"