# GORM ByteDance 开发指南

ByteDance 内部使用 `code.byted.org/gorm/bytedgen`（基于官方 `gorm/gen` 封装）进行 ORM 代码生成。

## 1. 代码生成工作流（make db）

### Makefile 结构

```makefile
PROJECT_DIR=$(shell dirname "$0")
GENERATE_DIR="$(PROJECT_DIR)/cmd/generate/generate.go"

db:
    @echo "Start Generating" && go run "$(GENERATE_DIR)"
```

执行 `make db` 时，会运行 `cmd/generate/generate.go`，完成以下步骤：
1. 初始化配置（`config.Init()`）
2. 初始化数据库连接（`dal.Init()`）
3. 配置代码生成器（`bytedgen.NewGenerator`）
4. 指定需要生成的表（`g.GenerateModelAs`）
5. 应用基础查询方法（`g.ApplyBasic`）
6. 执行生成（`g.Execute()`）

### generate.go 完整示例

```go
package main

import (
    "code.byted.org/gorm/bytedgen"
    "code.byted.org/pdi-qa/agent_report_service/biz/config"
    "code.byted.org/pdi-qa/agent_report_service/biz/infra/dal"

    "gorm.io/gen"
)

func main() {
    config.Init()

    // 初始化数据库连接
    dal.Init()

    // 配置生成器，OutPath 指定生成文件的输出目录
    g := bytedgen.NewGenerator(gen.Config{
        OutPath:       "biz/infra/dal/query",
        FieldNullable: true, // 可空字段生成为指针类型（*string, *int 等）
    })

    g.UseDB(dal.GetDB())

    // 注册需要生成的表：g.GenerateModelAs("数据库表名", "Go结构体名")
    issueReport     := g.GenerateModelAs("issue_report",      "IssueReport")
    issueItem       := g.GenerateModelAs("issue_item",        "IssueItem")
    issueSuggestion := g.GenerateModelAs("issue_suggestion",  "IssueSuggestion")

    // ApplyBasic 为每个模型生成基础 CRUD 方法
    g.ApplyBasic(issueReport)
    g.ApplyBasic(issueItem)
    g.ApplyBasic(issueSuggestion)

    g.Execute()
}
```

### 添加新表的步骤

1. 在数据库中创建新表（或确认表已存在）。
2. 在 `generate.go` 中添加对应的 `GenerateModelAs` 和 `ApplyBasic`：
   ```go
   newTable := g.GenerateModelAs("new_table_name", "NewTableModel")
   g.ApplyBasic(newTable)
   ```
3. 执行 `make db` 重新生成。
4. 生成后检查 `biz/infra/dal/query/` 下的新文件是否符合预期。

---

## 2. 生成文件结构

执行 `make db` 后，生成文件位于 `OutPath`（如 `biz/infra/dal/query/`）：

```text
biz/infra/dal/query/
├── gen.go                  # 初始化查询对象
├── issue_report.gen.go     # IssueReport 的查询方法
├── issue_item.gen.go
└── ...
```

**关键约定**：
- `.gen.go` 文件**不要手动修改**，每次 `make db` 都会覆盖。
- 自定义查询逻辑应写在单独的 Repository/DAO 层。

---

## 3. 使用生成的查询对象

### 初始化

```go
// dal/query 包由 gen.go 提供 Use() 初始化
import "code.byted.org/pdi-qa/agent_report_service/biz/infra/dal/query"

q := query.Use(db) // db 是 *gorm.DB 实例
```

### 基础 CRUD

#### 查询单条记录

```go
// 按主键查询
report, err := q.IssueReport.Where(q.IssueReport.ID.Eq(id)).Take()
if err != nil {
    return nil, err
}

// 按条件查询第一条
report, err := q.IssueReport.Where(q.IssueReport.Status.Eq("open")).First()
```

#### 查询多条记录

```go
reports, err := q.IssueReport.
    Where(q.IssueReport.ProjectID.Eq(projectID)).
    Order(q.IssueReport.CreatedAt.Desc()).
    Find()
```

#### 分页查询

```go
reports, err := q.IssueReport.
    Where(q.IssueReport.Status.Eq("open")).
    Offset(offset).
    Limit(pageSize).
    Find()
```

#### 创建记录

```go
report := &model.IssueReport{
    ProjectID: projectID,
    Title:     "Bug report",
    Status:    "open",
}
err := q.IssueReport.Create(report)
```

#### 更新记录

```go
// 按条件更新指定字段（推荐：避免零值问题）
_, err := q.IssueReport.
    Where(q.IssueReport.ID.Eq(id)).
    Update(q.IssueReport.Status, "closed")

// 更新多个字段
_, err := q.IssueReport.
    Where(q.IssueReport.ID.Eq(id)).
    Updates(map[string]interface{}{
        "status": "closed",
        "score":  0, // 零值可以安全更新，不会被忽略
    })
```

#### 删除记录

```go
// 软删除（模型含 DeletedAt 字段时）
_, err := q.IssueReport.Where(q.IssueReport.ID.Eq(id)).Delete()
```

---

## 4. 事务处理

### 推荐：闭包形式（自动提交/回滚）

```go
err := q.Transaction(func(tx *query.Query) error {
    if err := tx.IssueReport.Create(report); err != nil {
        return err // 自动回滚
    }
    if err := tx.IssueItem.Create(item); err != nil {
        return err // 自动回滚
    }
    return nil // 自动提交
})
```

### 手动事务（需要更细粒度控制时）

```go
tx := q.Begin()
defer func() {
    if r := recover(); r != nil {
        tx.Rollback()
    }
}()

if err := tx.IssueReport.Create(report).Error; err != nil {
    tx.Rollback()
    return err
}

tx.Commit()
```

---

## 5. 常见陷阱

| 陷阱 | 说明 | 正确做法 |
|------|------|----------|
| 零值更新被忽略 | `Updates(struct{})` 时，`0`/`""`/`false` 字段被跳过 | 用 `map[string]interface{}` 或按字段 `Update` |
| 直接修改 `.gen.go` 文件 | `make db` 会覆盖所有修改 | 自定义逻辑写在 Repository 层 |
| 忘记 `ApplyBasic` | 生成的结构体没有查询方法 | `g.GenerateModelAs` 后必须调用 `g.ApplyBasic` |
| 数据库连接未初始化 | `dal.Init()` 未调用导致 nil panic | 确保在 `g.UseDB` 前完成 `dal.Init()` |
| `First` vs `Take` | `First` 强制按主键排序，`Take` 不排序 | 不需要排序时用 `Take`，性能更好 |
| `First` 找不到记录 | 返回 `gorm.ErrRecordNotFound`，不是 nil | 用 `errors.Is(err, gorm.ErrRecordNotFound)` 判断 |

---

## 6. FieldNullable 与指针类型

当 `gen.Config.FieldNullable: true` 时，数据库中允许 NULL 的字段会生成为指针类型：

```go
// 数据库字段 description 允许 NULL
type IssueReport struct {
    ID          int64   `gorm:"column:id;primaryKey"`
    Title       string  `gorm:"column:title"`
    Description *string `gorm:"column:description"` // 可空 -> 指针类型
}
```

**使用时注意**：
```go
// 读取可空字段
if report.Description != nil {
    fmt.Println(*report.Description)
}

// 写入可空字段
desc := "some description"
report.Description = &desc

// 写入 NULL
report.Description = nil
```
