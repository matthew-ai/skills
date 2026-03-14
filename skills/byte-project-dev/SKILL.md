---
name: byte-project-dev
description: ByteDance 内部项目开发指南，涵盖 GORM（bytedgen 代码生成）、Hertz HTTP 框架（hertztool + Thrift IDL 生成）的使用规范。当用户询问 ByteDance 内部项目的数据库 ORM 生成、GORM 查询、Hertz HTTP 接口定义、hertztool 代码生成、Thrift IDL 编写等开发流程时使用。
---

# ByteDance 内部项目开发指南

本 Skill 提供 ByteDance 内部项目的核心开发规范，帮助快速上手内部工具链与框架。

## 能力范围

1. **GORM 代码生成**：使用 `bytedgen` 从数据库表结构自动生成 ORM 模型和查询代码。
2. **GORM 查询实践**：基于生成代码进行安全、高效的数据库操作。
3. **Hertz HTTP 框架**：使用 `hertztool` + Thrift IDL 生成 HTTP 服务端/客户端代码，实现 handler 业务逻辑。

## 参考文档

- **[GORM ByteDance 开发指南](references/gorm_bytedance.md)**：`make db` 工作流、`bytedgen` 代码生成、生成代码使用规范。
- **[Hertz ByteDance 开发指南](references/hertz_bytedance.md)**：`make hertz-update` 工作流、Thrift IDL 编写、handler 实现、中间件、新增接口完整流程。

## 快速参考

### GORM 代码生成流程

```bash
make db
# 等价于：go run cmd/generate/generate.go
```

生成文件位置：`biz/infra/dal/query/`（由 `gen.Config.OutPath` 配置）。

### Hertz 代码生成流程

```bash
make hertz-update
# 等价于：hertztool update -idl <入口thrift> && hertztool client -idl <入口thrift>
```

| 文件 | 生成方式 | 是否可修改 |
|------|---------|-----------|
| `biz/handler/**/*_method.go` | 增量更新 | **可以**，在此写业务逻辑 |
| `biz/model/` | 全量重新生成 | **不可以** |
| `biz/router/**/middleware.go` | 增量更新 | **可以**，在此加中间件 |
| `biz/router/**/*.go`（非middleware） | 全量重新生成 | **不可以** |

### 关键注意事项

- **bytedgen**：字节内部封装的 `gorm/gen`，入口 `code.byted.org/gorm/bytedgen`，生成前需 `dal.Init()` 连接数据库。
- **hertztool**：字节内部 Hertz 代码生成工具，入口 `code.byted.org/middleware/hertztool/v3`。
- **IDL 注解**：Hertz Thrift IDL 用 `api.body`/`api.query`/`api.path` 声明参数来源，用 `api.post`/`api.get` 等声明路由。

## 常见任务

- **添加新数据库表 ORM**：在 `cmd/generate/generate.go` 加 `GenerateModelAs` + `ApplyBasic`，然后 `make db`。
- **添加新 HTTP 接口**：在 IDL 里加 struct 和 service 方法，`make hertz-update`，再在 `_method.go` 实现业务逻辑。
- **事务操作**：优先使用 `db.Transaction(func(tx *gorm.DB) error {...})` 闭包形式。
