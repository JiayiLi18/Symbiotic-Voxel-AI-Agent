#This is an example that uses the websockets api to know when a prompt execution is done
#Once the prompt execution is done it downloads the images using the /history endpoint

import websocket #NOTE: websocket-client (https://github.com/websocket-client/websocket-client)
import uuid
import json
import urllib.request
import urllib.parse
import requests
import os

server_address = "127.0.0.1:8188"
client_id = str(uuid.uuid4())

def queue_prompt(prompt):
    p = {"prompt": prompt, "client_id": client_id}
    data = json.dumps(p).encode('utf-8')
    req =  urllib.request.Request("http://{}/prompt".format(server_address), data=data)
    return json.loads(urllib.request.urlopen(req).read())

def get_image(filename, subfolder, folder_type):
    data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
    url_values = urllib.parse.urlencode(data)
    with urllib.request.urlopen("http://{}/view?{}".format(server_address, url_values)) as response:
        return response.read()

def get_history(prompt_id):
    with urllib.request.urlopen("http://{}/history/{}".format(server_address, prompt_id)) as response:
        return json.loads(response.read())

def get_images(ws, prompt):
    print("开始执行工作流")
    prompt_id = queue_prompt(prompt)['prompt_id']
    output_images = {}
    while True:
        out = ws.recv()
        if isinstance(out, str):
            message = json.loads(out)
            if message['type'] == 'executing':
                data = message['data']
                if data['node'] is None and data['prompt_id'] == prompt_id:
                    print("工作流执行完成！")
                    break #Execution is done
        else:
            # If you want to be able to decode the binary stream for latent previews, here is how you can do it:
            # bytesIO = BytesIO(out[8:])
            # preview_image = Image.open(bytesIO) # This is your preview in PIL image format, store it in a global
            continue #previews are binary data

    print("正在获取历史记录...")
    history = get_history(prompt_id)[prompt_id]
    print("正在下载生成的图片...")
    for node_id in history['outputs']:
        node_output = history['outputs'][node_id]
        images_output = []
        if 'images' in node_output:
            for image in node_output['images']:
                print(f"正在下载图片: {image['filename']}")
                image_data = get_image(image['filename'], image['subfolder'], image['type'])
                images_output.append(image_data)
        output_images[node_id] = images_output

    return output_images

def upload_file(file, subfolder="", overwrite=False):
    try:
        # Wrap file in formdata so it includes filename
        body = {"image": file}
        data = {}
        
        if overwrite:
            data["overwrite"] = "true"
  
        if subfolder:
            data["subfolder"] = subfolder

        resp = requests.post(f"http://{server_address}/upload/image", files=body,data=data)
        
        if resp.status_code == 200:
            data = resp.json()
            # Add the file to the dropdown list and update the widget value
            path = data["name"]
            if "subfolder" in data:
                if data["subfolder"] != "":
                    path = data["subfolder"] + "/" + path
            

        else:
            print(f"{resp.status_code} - {resp.reason}")
    except Exception as error:
        print(error)
    return path

def call_comfyUI(input_image = "", pprompt="", nprompt="text", denoise = 1):
    """
    调用ComfyUI生成图片
    Args:
        input_image: 输入图片路径
        pprompt: 正面提示词
        nprompt: 负面提示词
        denoise: 降噪强度 (0-1)
    Returns:
        str: 生成的图片路径
    """
    # 检查正面提示词是否为空或只有空格
    if not pprompt.strip():
        print("错误：正面提示词不能为空！")
        return None
    
    print("开始执行图片生成流程...")
    
    # 加载工作流
    print("正在加载工作流...")
    try:
        with open("Minecraft_Texture_Workflow_API.json", "r", encoding="utf-8") as f:
            workflow_data = f.read()
        workflow = json.loads(workflow_data)
    except FileNotFoundError:
        print("错误：找不到工作流文件 Minecraft_Texture_Workflow_API.json")
        return None
    except json.JSONDecodeError:
        print("错误：工作流文件格式不正确")
        return None
    except Exception as e:
        print(f"错误：加载工作流时发生未知错误: {str(e)}")
        return None
    
    # 如果没有输入图片，则设置denoise为1
    if not input_image:
        print("警告: 未提供输入图片, 将使用默认降噪强度1,controlNet strength = 0")
        denoise = 1
        #
        workflow["3"]["inputs"]["strength"] = 0
    else:
        # 上传输入图片
        print(f"正在上传输入图片: {input_image}")
        with open(input_image, "rb") as f:
            comfyui_path_image = upload_file(f, "", True)
    
    # 设置提示词
    workflow["38"]["inputs"]["text"] = pprompt  # 正面提示词
    workflow["7"]["inputs"]["text"] = nprompt   # 负面提示词
    
    # 设置随机种子
    import random
    seed = random.randint(1, 1000000000)
    print(f"使用随机种子: {seed}")
    workflow["3"]["inputs"]["seed"] = seed
    
    # 设置输入图片（如果有）
    if input_image:
        workflow["54"]["inputs"]["image"] = comfyui_path_image
    
    # 设置降噪强度
    workflow["3"]["inputs"]["denoise"] = denoise
    
    # 连接WebSocket并执行工作流
    print("正在连接WebSocket...")
    ws = websocket.WebSocket()
    ws.connect("ws://{}/ws?clientId={}".format(server_address, client_id))
    print("WebSocket连接成功")
    
    # 获取生成的图片
    images = get_images(ws, workflow)
    ws.close()
    
    # 保存生成的图片
    print("正在保存生成的图片...")
    saved_images = []
    for node_id in images:
        for image_data in images[node_id]:
            from PIL import Image
            import io
            image = Image.open(io.BytesIO(image_data))
            output_dir = "output/image"
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.normpath(os.path.join(output_dir, f"Texture-{node_id}-{seed}.png")).replace("\\", "/")
            image.save(output_path)
            saved_images.append(output_path)
            print(f"图片已保存到: {output_path}")
    
    print("所有操作完成！")
    return output_path

# ---在此脚本中直接运行验证---
if __name__ == "__main__": #只有当这个脚本是被直接运行时，下面的代码才会执行。
    call_comfyUI("input/image/example.png", "Texture of dirt", "text, bad quality", 0.55)