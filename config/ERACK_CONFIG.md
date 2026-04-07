# ERack 数据库配置说明

## 配置文件概述

db-ai-server 已配置为 ERack 电子货架管理系统的数据库服务，支持自然语言到SQL的转换。

## 数据库连接配置

`config/server_config.json` 中的数据库连接已配置：

```json
{
  "database": {
    "connection_string": "mysql://root:matrixdb@localhost:3306/erack",
    "enable_direct_query": true
  }
}
```

**连接参数：**
- 主机：localhost
- 端口：3306
- 数据库：erack
- 用户名：root
- 密码：matrixdb

## 数据库表结构

ERack 系统包含以下6个核心表：

### 1. sys_user（用户表）
存储系统用户的基本信息。
- **主要字段：** id, name, password, role_id, real_name, enable
- **关键字段注释：**
  - `id` - 主键
  - `name` - 用户名
  - `password` - 密码（加密存储，敏感字段）
  - `role_id` - 角色Id
  - `real_name` - 用户真实名称
  - `enable` - 是否可用（1-可用，0-不可用）

### 2. sys_role（角色表）
存储系统角色信息。
- **主要字段：** id, name, description
- **关键字段注释：**
  - `id` - 主键
  - `name` - 角色名
  - `description` - 角色描述

### 3. permission（角色权限配置表）
存储角色与模块的权限映射。
- **主要字段：** id, role_id, module_category, module_name, permission_name, permission_code, create_time, update_time
- **关键字段注释：**
  - `role_id` - 角色Id
  - `module_category` - 模块分类
  - `module_name` - 模块名称
  - `permission_name` - 权限名称
  - `permission_code` - 权限编码

### 4. rack（电子货架表）
存储电子货架的配置信息。
- **主要字段：** id, no, layers, slots, gateway_ip, etag_gateway_ip, etag_gateway_port, light_gateway_ip, light_gateway_port, state, enable
- **关键字段注释：**
  - `id` - 主键
  - `no` - 货架编号
  - `layers` - 货架层数
  - `slots` - 每层槽位数
  - `gateway_ip` - 网关ip地址
  - `etag_gateway_ip` - 电子标签网关地址
  - `etag_gateway_port` - 电子标签网关端口
  - `light_gateway_ip` - 信号灯网关ip
  - `light_gateway_port` - 信号灯网关端口
  - `state` - 状态
  - `enable` - 是否可用（1-可用，0-不可用）

### 5. etag_address（电子标签地址表）
存储电子标签的地址映射关系。
- **主要字段：** id, layer, Slot, address, rack_id
- **关键字段注释：**
  - `layer` - 所属货架层
  - `Slot` - 所属货架槽
  - `address` - 电子标签地址
  - `rack_id` - 货架Id（外键关联rack表）

### 6. alarm_log（告警日志表）
记录告警日志。
- **主要字段：** id, task_id, alarm_code, res_code, alarm_level, content, created_date
- **关键字段注释：**
  - `task_id` - 任务Id
  - `alarm_code` - 告警代码
  - `res_code` - 资源代码
  - `alarm_level` - 告警级别
  - `content` - 告警内容
  - `created_date` - 创建时间

## 业务规则

### sys_user 表
- `password` 字段为敏感字段，查询时自动排除
- `enable` 字段：1表示用户可用，0表示不可用
- `name` 字段（用户名）可能有唯一约束

### sys_role 表
- `name` 字段（角色名）通常预定义，不建议随意修改
- 删除角色前需确认是否还有用户使用该角色

### rack 表
- `no` 字段（货架编号）有唯一约束
- `gateway_ip`、`etag_gateway_ip`、`light_gateway_ip` 都有唯一约束
- `enable` 字段：1表示货架可用，0表示不可用
- `state` 字段表示货架的运行状态

### etag_address 表
- `rack_id` 和 `address` 的组合有唯一约束
- `rack_id`、`layer`、`Slot` 的组合有唯一约束
- `layer` 表示所属货架层，`Slot` 表示所属货架槽
- `address` 表示电子标签的物理地址

### alarm_log 表
- `alarm_level` 表示告警级别（数字越大越严重）
- 告警日志通常只查询，不建议UPDATE或DELETE
- `created_date` 是告警发生时间

### permission 表
- `role_id` 关联 sys_role 表的 id
- `module_category` 和 `module_name` 表示模块分类和名称
- `permission_code` 是权限的唯一标识

## 支持的查询示例

### 用户相关
1. "查询所有启用的用户"
2. "查询所有用户及其角色名称"
3. "查询角色为operator的用户"

### 货架相关
1. "查询所有货架信息"
2. "查询所有启用的货架"
3. "查询货架编号为E-Rack-1的详细信息"

### 电子标签相关
1. "查询货架编号为E-Rack-1的所有电子标签地址"
2. "查询货架第1层第1槽的电子标签地址"

### 告警日志相关
1. "查询最近的告警日志"
2. "查询告警级别为3的告警日志"
3. "查询今天的告警记录"

### 权限相关
1. "查询operator角色的所有权限"
2. "查询货架管理模块的权限配置"

## 特殊说明

1. **字段注释获取**：db-ai-server 已实现从数据库 `INFORMATION_SCHEMA.COLUMNS` 表查询字段注释的功能，查询结果会包含 `column_comments` 字段。

2. **列头显示**：ERack 端的通用查询功能会优先显示字段注释作为DataGrid列头，格式为 `注释内容 (字段名)`。

3. **敏感字段保护**：`sys_user.password` 等敏感字段会被自动排除在查询结果之外。

4. **性能优化**：大表查询会自动添加 `LIMIT` 限制，默认限制为100条。

## 启动服务

```bash
cd e:/develop/db-ai-server
python src/mcp_server.py
```

## 测试连接

确保以下服务已启动：
1. MySQL 数据库（erack）已创建并运行
2. Ollama 服务（http://localhost:11434）已启动
3. db-ai-server 已启动

## 配置文件位置

- 数据库Schema配置：`config/database_schema.json`
- 提示词配置：`config/prompts.json`
- 服务器配置：`config/server_config.json`
- 安全规则：`config/security_rules.json`
