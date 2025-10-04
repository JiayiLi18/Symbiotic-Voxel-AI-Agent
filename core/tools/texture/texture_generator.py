import os
import json
import uuid
import websocket
import urllib.request
import urllib.parse
import requests
from typing import Optional, Dict, List
from datetime import datetime
from PIL import Image
import io
import logging
from core.models.base import VoxelFace

# 配置日志
logger = logging.getLogger(__name__)

class TextureGenerator:
    def __init__(self, server_address: str = "127.0.0.1:8188"):
        self.server_address = server_address #ComfyUI服务器地址
        self.client_id = str(uuid.uuid4())
        from core.tools.config import get_paths_config
        cfg = get_paths_config()
        self.input_tex_dir = cfg.textures_dir
        self.output_tex_dir = cfg.textures_dir
        self.workflow_path = "Minecraft Texture Workflow v2.json"

    async def generate_texture(self, 
                             tex_name: str, 
                             pprompt: str,
                             nprompt: str = "text, blurry, watermark",
                             reference_image: Optional[str] = None) -> str:
        """
        生成纹理的主要方法 - 极简版本，只处理核心纹理生成
        Args:
            tex_name: 纹理名称
            pprompt: 正面提示词
            nprompt: 负面提示词
            reference_image: 参考图片文件名
        Returns:
            str: 生成的纹理文件名
        """
        try:
            logger.info("Starting texture generation")
            logger.info(f"Parameters: tex_name={tex_name}")
            logger.info(f"Prompt: {pprompt}")
            
            # 验证输入
            if not pprompt:
                raise ValueError("pprompt must be provided")
            
            if not tex_name:
                tex_name = pprompt[:10] if pprompt else "texture"
            
            # 加载工作流
            workflow = self._load_workflow()
            
            # 构建参考图片完整路径
            full_reference_path = None
            if reference_image:
                full_reference_path = os.path.join(self.input_tex_dir, reference_image)
                if not os.path.exists(full_reference_path):
                    logger.warning(f"Reference image not found: {reference_image}")
                else:
                    logger.info(f"Using reference image: {full_reference_path}")
            
            # 配置工作流参数
            configured_workflow = self._configure_workflow(
                workflow,
                pprompt,
                nprompt,
                full_reference_path
            )
            
            # 执行工作流并获取结果
            texture_name = await self._execute_workflow(
                configured_workflow,
                tex_name
            )
            
            if texture_name:
                logger.info(f"Successfully generated texture: {texture_name}")
                return texture_name
            else:
                logger.warning("No texture generated")
                return ""
            
        except Exception as e:
            logger.error(f"Error in generate_texture: {str(e)}", exc_info=True)
            return ""


    def _load_workflow(self) -> Dict:
        """加载ComfyUI工作流"""
        try:
            with open(self.workflow_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            raise RuntimeError(f"Failed to load workflow: {str(e)}")

    def _configure_workflow(self, 
                          workflow: Dict, 
                          pprompt: str,
                          nprompt: str,
                          reference_image: Optional[str] = None) -> Dict:
        """配置工作流参数"""
        # 设置提示词
        workflow["38"]["inputs"]["text"] = pprompt
        workflow["7"]["inputs"]["text"] = nprompt
        
        # 设置随机种子
        import random
        workflow["3"]["inputs"]["seed"] = random.randint(1, 1000000000)
        
        # 配置输入图片
        if reference_image and os.path.exists(reference_image):
            with open(reference_image, "rb") as f:
                image_path = self._upload_file(f)
            workflow["54"]["inputs"]["image"] = image_path
            #有图片则denoise为0.5, controlnet强度为0.5
            workflow["3"]["inputs"]["denoise"] = 0.5
            workflow["3"]["inputs"]["latent_image"] = ["61", 0] # 使用输入图片作为latent image
            workflow["58"]["inputs"]["strength"] = 0.5 #controlnet强度
        else: #无输入图片则使用空白图片并把降噪强度、controlnet强度设为默认
            workflow["3"]["inputs"]["denoise"] = 1.0
            workflow["3"]["inputs"]["latent_image"] = ["79", 0] # 使用空白图片作为latent image
            
            workflow["58"]["inputs"]["strength"] = 0 #controlnet强度归0
            
        return workflow

    async def _execute_workflow(self, workflow: Dict, tex_name: str) -> Optional[str]:
        """执行工作流并保存结果"""
        # 连接WebSocket
        ws = websocket.WebSocket()
        ws.connect(f"ws://{self.server_address}/ws?clientId={self.client_id}")
        
        try:
            # 获取生成的图片
            images = self._get_images(ws, workflow)
            
            # 保存图片
            for node_id in images:
                if node_id == "75":  # 输出节点
                    for image_data in images[node_id]:
                        # 保存图片
                        image = Image.open(io.BytesIO(image_data))
                        # 生成3位随机编号防止重复
                        import random
                        random_num = random.randint(100, 999)
                        filename = f"{tex_name}-{random_num}"
                        
                        os.makedirs(self.output_tex_dir, exist_ok=True)
                        output_path = os.path.join(
                            self.output_tex_dir, 
                            f"{filename}.png"
                        ).replace("\\", "/")
                        
                        image.save(output_path)
                        return filename
                        
        finally:
            ws.close()
            
        return None

    def _upload_file(self, file, subfolder: str = "", overwrite: bool = True) -> str:
        """上传文件到ComfyUI服务器"""
        try:
            body = {"image": file}
            data = {"overwrite": "true"} if overwrite else {}
            
            if subfolder:
                data["subfolder"] = subfolder

            resp = requests.post(
                f"http://{self.server_address}/upload/image",
                files=body,
                data=data
            )
            
            if resp.status_code == 200:
                data = resp.json()
                path = data["name"]
                if "subfolder" in data and data["subfolder"]:
                    path = f"{data['subfolder']}/{path}"
                return path
                    
            raise RuntimeError(f"Upload failed: {resp.status_code} - {resp.reason}")
            
        except Exception as e:
            raise RuntimeError(f"Upload error: {str(e)}")

    def _queue_prompt(self, prompt: Dict) -> Dict:
        """将提示词加入队列"""
        data = json.dumps({
            "prompt": prompt,
            "client_id": self.client_id
        }).encode('utf-8')
        
        req = urllib.request.Request(
            f"http://{self.server_address}/prompt",
            data=data
        )
        return json.loads(urllib.request.urlopen(req).read())

    def _get_images(self, ws: websocket.WebSocket, prompt: Dict) -> Dict[str, List[bytes]]:
        """获取生成的图片"""
        prompt_id = self._queue_prompt(prompt)['prompt_id']
        output_images = {}
        
        # 等待执行完成
        while True:
            out = ws.recv()
            if isinstance(out, str):
                message = json.loads(out)
                if (message['type'] == 'executing' and 
                    message['data']['node'] is None and 
                    message['data']['prompt_id'] == prompt_id):
                    break
                    
        # 获取历史记录
        history = self._get_history(prompt_id)[prompt_id]
        
        # 下载生成的图片
        for node_id in history['outputs']:
            node_output = history['outputs'][node_id]
            if 'images' in node_output:
                output_images[node_id] = [
                    self._get_image(
                        image['filename'],
                        image['subfolder'],
                        image['type']
                    )
                    for image in node_output['images']
                ]
                
        return output_images

    def _get_history(self, prompt_id: str) -> Dict:
        """获取历史记录"""
        with urllib.request.urlopen(
            f"http://{self.server_address}/history/{prompt_id}"
        ) as response:
            return json.loads(response.read())

    def _get_image(self, filename: str, subfolder: str, folder_type: str) -> bytes:
        """获取单个图片"""
        data = {
            "filename": filename,
            "subfolder": subfolder,
            "type": folder_type
        }
        url_values = urllib.parse.urlencode(data)
        with urllib.request.urlopen(
            f"http://{self.server_address}/view?{url_values}"
        ) as response:
            return response.read()

if __name__ == "__main__":
    import asyncio
    
    # 创建生成器实例（使用默认地址）
    generator = TextureGenerator()
    
    # 运行测试
