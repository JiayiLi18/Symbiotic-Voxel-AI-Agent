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

class TextureGenerator:
    def __init__(self, server_address: str = "127.0.0.1:8188"):
        self.server_address = server_address
        self.client_id = str(uuid.uuid4())
        self.output_tex_dir = r"C:\Aalto\S4\Graduation\AI-Agent\Assets\Resources\VoxelTextures"
        self.workflow_path = "Minecraft_Texture_Workflow_API.json"

    async def generate_texture(self, 
                             tex_name: str, 
                             pprompt: str, 
                             nprompt: str = "text, blurry, watermark",
                             denoise: float = 1.0,
                             input_image: str = "") -> Optional[str]:
        """
        生成纹理的主要方法
        Args:
            tex_name: 纹理名称
            pprompt: 正面提示词
            nprompt: 负面提示词
            denoise: 降噪强度 (0-1)
            input_image: 可选的输入图片路径
        Returns:
            str: 生成的纹理名称（不含扩展名）
        """
        try:
            # 验证输入
            if not pprompt.strip():
                raise ValueError("Positive prompt cannot be empty")
            
            if not tex_name:
                tex_name = pprompt[:20]  # 使用提示词前20个字符作为名称
            
            # 加载工作流
            workflow = self._load_workflow()
            
            # 配置工作流参数
            workflow = self._configure_workflow(
                workflow,
                pprompt,
                nprompt,
                denoise,
                input_image
            )
            
            # 执行工作流并获取结果
            texture_name = await self._execute_workflow(workflow, tex_name)
            
            return texture_name
            
        except Exception as e:
            print(f"Error generating texture: {str(e)}")
            return None

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
                          denoise: float,
                          input_image: str = "") -> Dict:
        """配置工作流参数"""
        # 设置提示词
        workflow["38"]["inputs"]["text"] = pprompt
        workflow["7"]["inputs"]["text"] = nprompt
        
        # 设置随机种子
        import random
        workflow["3"]["inputs"]["seed"] = random.randint(1, 1000000000)
        
        # 配置输入图片和降噪
        if input_image:
            with open(input_image, "rb") as f:
                image_path = self._upload_file(f)
            workflow["54"]["inputs"]["image"] = image_path
            workflow["3"]["inputs"]["strength"] = denoise
        else:
            workflow["3"]["inputs"]["denoise"] = 1.0
            workflow["3"]["inputs"]["strength"] = 0
            
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
                        timestamp = int(datetime.now().timestamp() * 1000)
                        filename = f"{tex_name}-{timestamp}"
                        
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
