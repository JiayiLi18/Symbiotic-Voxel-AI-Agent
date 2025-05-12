import os
import glob
from PIL import Image


#output_dir = r"C:\Aalto\S4\Graduation\AI-Agent\Assets\Resources\VoxelTextures"
output_tex_dir = "output/tiles"
output_texture_sheet_dir = "output/texture_sheet"

class TextureSheetGenerator:
    def __init__(self, textures_dir, output_path, sheet_size=(512, 512), tile_size=(16, 16)):
        """
        初始化贴图表生成器
        
        Args:
            textures_dir: 纹理贴图所在的目录
            output_path: 输出texture sheet的路径
            sheet_size: texture sheet的大小，默认为 (512, 512)
            tile_size: 每个贴图的大小，默认为 (16, 16)
        """
        self.textures_dir = textures_dir
        self.output_path = output_path
        self.sheet_size = sheet_size
        self.tile_size = tile_size
        
        # 计算网格大小
        self.grid_width = sheet_size[0] // tile_size[0]
        self.grid_height = sheet_size[1] // tile_size[1]
        self.total_slots = self.grid_width * self.grid_height
        
        # 保存贴图位置映射 {贴图名称: 位置索引}
        self.texture_positions = {}
        
        # 保存索引到贴图名称的映射 {位置索引: 贴图名称}
        self.index_to_texture = {}
        
        # 如果位置映射文件存在，则加载它
        self._load_positions_map()
    
    def _load_positions_map(self):
        """加载现有的位置映射文件（如果存在）"""
        positions_file = os.path.splitext(self.output_path)[0] + "_positions.json"
        if os.path.exists(positions_file):
            try:
                import json
                with open(positions_file, "r") as f:
                    loaded_positions = json.load(f)
                
                # 只保留实际存在的贴图位置映射
                for texture_name, index in loaded_positions.items():
                    texture_path = os.path.join(self.textures_dir, texture_name)
                    if os.path.exists(texture_path):
                        # 贴图文件存在，保留映射
                        self.texture_positions[texture_name] = int(index)
                        self.index_to_texture[int(index)] = texture_name
                
                print(f"已加载现有的位置映射文件: {positions_file}")
                print(f"加载了 {len(self.texture_positions)} 个有效贴图位置")
            except Exception as e:
                print(f"加载位置映射文件时出错: {str(e)}")
                self.texture_positions = {}
                self.index_to_texture = {}
    
    def get_texture_files(self, pattern="Texture-*.png"):
        """获取目录中所有的贴图文件"""
        return glob.glob(os.path.join(self.textures_dir, pattern))
    
    def create_texture_sheet(self, reset_positions=False):
        """
        创建纹理表并记录每个贴图的位置
        
        Args:
            reset_positions: 是否重置所有位置映射（如果为True，则忽略现有映射）
        """
        # 如果需要重置位置映射
        if reset_positions:
            self.texture_positions = {}
            self.index_to_texture = {}
            print("已重置所有位置映射")
        
        # 创建一个透明背景的图像
        sheet = Image.new("RGBA", self.sheet_size, (0, 0, 0, 0))
        
        # 获取所有贴图文件
        texture_files = self.get_texture_files()
        print(f"找到 {len(texture_files)} 个贴图文件")
        
        # 确保不超过总槽位数
        if len(texture_files) > self.total_slots:
            print(f"警告: 贴图文件数量 ({len(texture_files)}) 超过了可用槽位 ({self.total_slots})，部分贴图将被忽略")
            texture_files = texture_files[:self.total_slots]
        
        # 记录已使用的索引
        used_indices = set(self.texture_positions.values())
        next_index = 0
        
        # 遍历所有贴图并放置到表中
        for texture_path in texture_files:
            try:
                texture_name = os.path.basename(texture_path)
                
                # 检查该贴图是否已有位置
                if texture_name in self.texture_positions:
                    # 使用现有位置
                    index = self.texture_positions[texture_name]
                else:
                    # 分配新位置
                    # 找到下一个可用索引
                    while next_index in used_indices and next_index < self.total_slots:
                        next_index += 1
                    
                    if next_index >= self.total_slots:
                        print(f"警告: 没有可用的槽位给贴图 {texture_name}，跳过")
                        continue
                    
                    index = next_index
                    used_indices.add(index)
                    next_index += 1
                
                # 计算在网格中的位置
                grid_x = index % self.grid_width
                grid_y = index // self.grid_width
                
                # 计算像素位置
                x = grid_x * self.tile_size[0]
                y = grid_y * self.tile_size[1]
                
                # 打开贴图
                texture = Image.open(texture_path)
                
                # 将贴图粘贴到表中
                sheet.paste(texture, (x, y))
                
                # 记录贴图位置
                self.texture_positions[texture_name] = index
                self.index_to_texture[index] = texture_name
                
                print(f"已添加贴图 {texture_name} 到位置 {index} (坐标: {grid_x}, {grid_y})")
            except Exception as e:
                print(f"处理贴图 {texture_path} 时出错: {str(e)}")
        
        # 保存texture sheet
        os.makedirs(os.path.dirname(self.output_path), exist_ok=True)
        sheet.save(self.output_path)
        print(f"Texture sheet 已保存到: {self.output_path}")
        
        # 保存位置映射
        self.save_positions_map()
        
        return self.texture_positions
    
    def update_single_texture(self, texture_path, index=None, texture_name=None):
        """
        更新单个贴图到texture sheet中
        
        Args:
            texture_path: 要更新的贴图路径
            index: 要放置的位置索引 (如果为None, 则使用texture_name或尝试找到现有位置)
            texture_name: 贴图名称 (如果为None, 则从文件路径提取)
            
        Returns:
            int: 贴图的位置索引
        """
        if not os.path.exists(texture_path):
            raise FileNotFoundError(f"贴图文件不存在: {texture_path}")
        
        # 获取贴图名称
        if texture_name is None:
            texture_name = os.path.basename(texture_path)
        
        # 加载现有的texture sheet
        sheet_path = self.output_path
        if os.path.exists(sheet_path):
            sheet = Image.open(sheet_path)
        else:
            # 如果不存在，创建一个新的
            sheet = Image.new("RGBA", self.sheet_size, (0, 0, 0, 0))
        
        # 确定位置索引
        if index is None:
            # 如果没有提供索引，检查是否已有这个贴图
            if texture_name in self.texture_positions:
                index = self.texture_positions[texture_name]
                print(f"使用现有位置索引 {index} 更新贴图 {texture_name}")
            else:
                # 找到下一个可用索引
                used_indices = set(self.texture_positions.values())
                for i in range(self.total_slots):
                    if i not in used_indices:
                        index = i
                        break
                else:
                    raise ValueError(f"没有可用的槽位来添加新贴图 {texture_name}")
                print(f"使用新位置索引 {index} 添加贴图 {texture_name}")
        
        # 检查索引是否有效
        if index < 0 or index >= self.total_slots:
            raise ValueError(f"位置索引 {index} 无效，必须在 0-{self.total_slots-1} 范围内")
        
        # 计算在网格中的位置
        grid_x = index % self.grid_width
        grid_y = index // self.grid_width
        
        # 计算像素位置
        x = grid_x * self.tile_size[0]
        y = grid_y * self.tile_size[1]
        
        # 打开贴图
        texture = Image.open(texture_path)
        
        # 将贴图粘贴到表中
        sheet.paste(texture, (x, y))
        
        # 更新位置映射
        self.texture_positions[texture_name] = index
        self.index_to_texture[index] = texture_name
        
        # 保存更新后的texture sheet
        sheet.save(sheet_path)
        print(f"贴图 {texture_name} 已更新到位置 {index}")
        
        # 保存更新后的位置映射
        self.save_positions_map()
        
        return index
    
    def get_index_by_name(self, texture_name):
        """
        通过贴图名称获取索引
        
        Args:
            texture_name: 贴图名称
            
        Returns:
            int: 贴图的位置索引（如果不存在则返回None）
        """
        return self.texture_positions.get(texture_name)
    
    def get_name_by_index(self, index):
        """
        通过索引获取贴图名称
        
        Args:
            index: 位置索引
            
        Returns:
            str: 贴图名称（如果不存在则返回None）
        """
        return self.index_to_texture.get(index)
    
    def get_name_by_texture_prefix(self, prefix):
        """
        通过贴图名称前缀获取完整贴图名称
        
        Args:
            prefix: 贴图名称前缀（例如'dirt'会匹配'Texture-dirt-123456.png'）
            
        Returns:
            str: 匹配的第一个贴图名称（如果不存在则返回None）
        """
        for name in self.texture_positions.keys():
            if f"Texture-{prefix}-" in name:
                return name
        return None
    
    def get_index_by_texture_prefix(self, prefix):
        """
        通过贴图名称前缀获取索引
        
        Args:
            prefix: 贴图名称前缀（例如'dirt'会匹配'Texture-dirt-123456.png'）
            
        Returns:
            int: 贴图的位置索引（如果不存在则返回None）
        """
        name = self.get_name_by_texture_prefix(prefix)
        if name:
            return self.texture_positions.get(name)
        return None
    
    def save_positions_map(self, output_path=None):
        """保存贴图位置映射到文件"""
        if not output_path:
            output_path = os.path.splitext(self.output_path)[0] + "_positions.json"
        
        import json
        with open(output_path, "w") as f:
            json.dump(self.texture_positions, f, indent=4)
        
        print(f"贴图位置映射已保存到: {output_path}")
        print(f"共 {len(self.texture_positions)} 个贴图位置被记录")
        return output_path


def repair_texture_sheet():
    """简单重新生成texture sheet，修复位置映射问题"""
    print("\n开始修复texture sheet和位置映射...")
    
    output_sheet_path = os.path.join(output_texture_sheet_dir, "texture_sheet.png")
    generator = TextureSheetGenerator(output_tex_dir, output_sheet_path)
    
    # 是否重置所有位置
    reset = input("是否重置所有位置映射？(y/n): ").strip().lower() == 'y'
    
    # 重新生成texture sheet
    generator.create_texture_sheet(reset_positions=reset)
    print("texture sheet修复完成")
    
    return output_sheet_path


if __name__ == "__main__":
    
    # 修复texture sheet
    repair_texture_sheet()
   
   
    