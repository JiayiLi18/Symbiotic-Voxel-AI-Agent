# core/tools/voxel/build.py
from typing import List, Dict, Tuple, Optional
from core.models.game_state import GameState
from core.tools.database.voxel_db import VoxelDatabase

class VoxelBuilder:
    def __init__(self, db_path: str):
        self.voxel_db = VoxelDatabase(db_path)
    
    #TODO: 添加一些固定化的建造功能，优先级比较低