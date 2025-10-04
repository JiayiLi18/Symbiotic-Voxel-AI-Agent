# ID生成器集成完成

## ✅ 实现的功能

### 1. ID生成器工具模块
- **位置**: `core/utils/id_generator.py`
- **功能**: 提供统一的ID生成方法
- **导出**: `new_session_id()`, `new_goal_id()`, `new_plan_id()`, `new_command_id()`

### 2. 责任分工

#### Unity端负责：
- **Session ID**: 可以使用Python生成的ID，也可以自己生成（只要符合格式）

#### Python端负责：
- **Goal ID**: Planner生成新目标时 (`core/tools/planner.py`)
- **Plan ID**: Planner生成计划步骤时 (`core/tools/planner.py`) 
- **Command ID**: Executor执行计划时 (`core/tools/execute.py`)

### 3. 集成点

#### Planner集成 (`core/tools/planner.py`)
```python
# 导入ID生成器
from core.utils.id_generator import new_goal_id, new_plan_id

# 新增函数：_generate_proper_ids()
# 作用：将OpenAI返回的任意格式ID替换为规范格式

# 使用场景：
# 1. OpenAI返回 {"goal_id": "build_castle"} 
# 2. 替换为 {"goal_id": "goal_ek30_001"}
# 3. 为每个plan生成正确的plan_id: "plan_001_01", "plan_001_02"
```

#### Executor集成 (`core/tools/execute.py`)
```python
# 导入ID生成器
from core.utils.id_generator import new_command_id

# 更新命令ID生成：
# 旧：self._command_counter += 1 (纯数字)
# 新：new_command_id(plan_id, sequence) (规范格式)

# 支持每个plan独立的命令序号
```

#### SessionManager集成 (`core/tools/session/manager.py`)
```python
# 导入ID生成器
from core.utils.id_generator import new_session_id

# 新增方法：get_or_create_session()
# 作用：如果没有session_id，自动生成一个
```

## 🔄 数据流程

### 完整的ID生成流程：

```
1. 用户访问 -> SessionManager.get_or_create_session()
   └── 生成: sess_20250909_163532_ek30

2. 用户请求 -> Planner.plan_async()
   ├── OpenAI返回任意格式ID
   ├── _generate_proper_ids() 标准化
   ├── 生成: goal_ek30_001
   └── 生成: plan_001_01, plan_001_02, plan_001_03

3. 执行计划 -> Executor.execute_function()
   └── 生成: cmd_plan_001_01_001, cmd_plan_001_02_001, ...
```

### 层级关系示例：
```
sess_20250909_163532_ek30
├── goal_ek30_001 "Build medieval castle"
│   ├── plan_001_01 "Create stone texture"
│   │   └── cmd_plan_001_01_001 (generate_texture)
│   ├── plan_001_02 "Create stone voxel"
│   │   └── cmd_plan_001_02_001 (create_voxel_type)
│   └── plan_001_03 "Build foundation"
│       ├── cmd_plan_001_03_001 (place_block step 1)
│       └── cmd_plan_001_03_002 (place_block step 2)
```

## 🎯 解决的问题

### 之前的问题：
- ❌ ID生成器创建了但没有使用
- ❌ 责任分工不明确
- ❌ OpenAI可能返回任意格式的ID
- ❌ Command ID使用简单递增数字

### 现在的解决方案：
- ✅ 明确的责任分工：Unity负责Session，Python负责Goal/Plan/Command
- ✅ Planner自动标准化OpenAI返回的ID
- ✅ Executor使用规范的Command ID格式
- ✅ 所有ID都有清晰的层级关系和可追溯性

## 🧪 测试验证

### 演示脚本：`test_id_generator.py`
运行结果展示了完整的ID生成流程，证明：
1. 所有ID格式符合规范
2. 层级关系清晰可追溯
3. 每个组件职责明确

### 使用方式：
```bash
python test_id_generator.py
```

## 📋 下一步

现在ID生成器已经完全集成，可以：

1. **测试Planner**: 使用 `test_planner_data.json` 测试，验证ID生成
2. **Unity集成**: Unity端只需要确保发送的Session ID符合格式（或使用Python生成的）
3. **生产部署**: 所有ID都会自动使用统一格式，便于调试和维护

## 🔧 技术细节

### 智能ID替换
Planner中的 `_generate_proper_ids()` 函数会：
- 检查OpenAI返回的ID格式
- 如果不符合规范，自动替换为标准格式
- 处理depends_on引用，确保引用的ID也是正确格式
- 保持向后兼容性

### 灵活的Command计数
Executor中每个plan都有独立的命令计数器：
- `self._command_counters = {"plan_001_01": 2, "plan_001_02": 1}`
- 支持同一个plan生成多个commands
- 每个command都有唯一且可追溯的ID

现在ID系统完全统一且自动化！🎉
