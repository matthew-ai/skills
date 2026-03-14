# Hertz (HTTP) ByteDance 开发指南

ByteDance 内部使用 `hertztool`（基于 Hertz 框架封装）通过 Thrift IDL 生成 HTTP 服务端和客户端代码。

## 1. 代码生成工作流（make hertz-update）

### Makefile 结构

```makefile
PROJECT_DIR=$(shell dirname "$0")

hertz-update:
    @echo "hertztool-update"
    @cd $(PROJECT_DIR) && go install code.byted.org/middleware/hertztool/v3@latest && hertztool update -idl idl/report/service.thrift && hertztool client -idl idl/report/service.thrift
```

执行 `make hertz-update` 时，依次完成：
1. **安装工具**：`go install` 确保 `hertztool` 为最新版本。
2. **更新服务端代码**：`hertztool update -idl <入口thrift文件>` 根据 IDL 增量更新 handler、model、router。
3. **生成客户端代码**：`hertztool client -idl <入口thrift文件>` 生成调用该服务的客户端 SDK。

### 增量更新规则

| 文件/目录 | update 行为 |
|-----------|------------|
| `biz/handler/**/*_method.go` | **增量更新**：新增方法追加，已有方法不覆盖 |
| `biz/model/` | **全量重新生成**，不要手动修改 |
| `biz/router/**/hello.go` | **全量重新生成**，不要手动修改 |
| `biz/router/**/middleware.go` | **增量更新**，可添加自定义中间件 |
| `router_gen.go` | **全量重新生成**，不要手动修改 |

**核心原则**：只在标注「增量更新」的文件里写业务代码，「全量重新生成」的文件不要手动修改。

---

## 2. 生成项目结构

```text
.
├── biz/
│   ├── handler/                        # 业务处理层（在此实现接口逻辑）
│   │   ├── report/
│   │   │   └── report_service.go       # IDL service 方法实现，update 增量更新
│   │   └── ping.go                     # 内置健康检查，无需修改
│   ├── model/                          # IDL 生成的数据结构（勿手动修改）
│   │   └── report/
│   │       └── service/
│   │           └── service.go          # Thrift IDL 对应的 Go 结构体
│   └── router/                         # 路由注册代码（勿手动修改生成部分）
│       ├── report/
│       │   └── service/
│       │       ├── service.go          # 路由注册，update 重新生成
│       │       └── middleware.go       # 中间件，update 增量更新
│       └── register.go
├── idl/
│   └── report/
│       └── service.thrift              # IDL 入口文件
├── main.go                             # 程序入口
├── router.go                           # 用户自定义路由（非IDL路由在此注册）
└── router_gen.go                       # IDL 路由注册入口（勿手动修改）
```

---

## 3. Thrift IDL 定义（Hertz HTTP）

Hertz 的 IDL 使用标准 Thrift 语法，通过注解声明 HTTP 路由信息。

### 基础结构

```thrift
namespace go report.service   // 对应生成的 Go 包路径：biz/model/report/service

// 请求结构体
struct CreateReportRequest {
    1: required string project_id (api.body="project_id")  // JSON body 字段
    2: required string title      (api.body="title")
    3: optional string description (api.body="description")
}

// 响应结构体
struct CreateReportResponse {
    1: required i32    code    (api.body="code")
    2: required string message (api.body="message")
    3: optional Report data    (api.body="data")
}

struct Report {
    1: required i64    id         (api.body="id")
    2: required string project_id (api.body="project_id")
    3: required string title      (api.body="title")
}

// 服务定义
service ReportService {
    // POST 接口
    CreateReportResponse CreateReport(1: CreateReportRequest req) (
        api.post="/api/v1/report/create"
    )

    // GET 接口（路径参数 + query 参数）
    GetReportResponse GetReport(1: GetReportRequest req) (
        api.get="/api/v1/report/:report_id"
    )

    // PUT 接口
    UpdateReportResponse UpdateReport(1: UpdateReportRequest req) (
        api.put="/api/v1/report/:report_id"
    )

    // DELETE 接口
    BaseResponse DeleteReport(1: DeleteReportRequest req) (
        api.delete="/api/v1/report/:report_id"
    )
}
```

### 参数注解说明

| 注解 | 来源 | 示例 |
|------|------|------|
| `api.body` | JSON 请求体 | `(api.body="field_name")` |
| `api.query` | URL Query 参数 | `(api.query="page")` |
| `api.path` | URL 路径参数 | `(api.path="report_id")` |
| `api.header` | 请求头 | `(api.header="X-Token")` |
| `api.post` | POST 路由 | `(api.post="/api/v1/xxx")` |
| `api.get` | GET 路由 | `(api.get="/api/v1/xxx")` |
| `api.put` | PUT 路由 | `(api.put="/api/v1/xxx")` |
| `api.delete` | DELETE 路由 | `(api.delete="/api/v1/xxx")` |

### GET 接口的请求结构体示例

```thrift
struct GetReportRequest {
    1: required string report_id (api.path="report_id")    // 路径参数 /report/:report_id
    2: optional i32    page      (api.query="page")         // query 参数 ?page=1
    3: optional i32    page_size (api.query="page_size")    // query 参数 ?page_size=20
}
```

---

## 4. 实现 Handler 业务逻辑

`make hertz-update` 后，在 `biz/handler/` 下找到对应的 `*_method.go` 文件实现业务逻辑。

### Handler 函数签名

```go
// biz/handler/report/report_service.go
package report

import (
    "context"

    "github.com/cloudwego/hertz/pkg/app"
    "github.com/cloudwego/hertz/pkg/protocol/consts"

    report_service "code.byted.org/xxx/biz/model/report/service"
)

// CreateReport 实现 IDL 中定义的 CreateReport 方法
func CreateReport(ctx context.Context, c *app.RequestContext) {
    var err error
    var req report_service.CreateReportRequest

    // 1. 绑定并校验请求参数
    err = c.BindAndValidate(&req)
    if err != nil {
        c.JSON(consts.StatusBadRequest, map[string]interface{}{
            "code":    400,
            "message": err.Error(),
        })
        return
    }

    // 2. 实现业务逻辑
    resp := new(report_service.CreateReportResponse)
    // ... 调用 service 层
    resp.Code = 0
    resp.Message = "success"

    // 3. 返回响应
    c.JSON(consts.StatusOK, resp)
}
```

### 获取路径参数和 Query 参数

```go
func GetReport(ctx context.Context, c *app.RequestContext) {
    var req report_service.GetReportRequest
    err := c.BindAndValidate(&req)
    if err != nil {
        c.JSON(consts.StatusBadRequest, map[string]interface{}{"code": 400, "message": err.Error()})
        return
    }

    // req.ReportId 已从路径参数自动绑定（api.path="report_id"）
    // req.Page 已从 query 参数自动绑定（api.query="page"）
    reportID := req.ReportId
    _ = reportID
}
```

### 统一响应格式

建议在项目中定义统一的响应工具函数：

```go
// biz/utils/response.go
func Success(c *app.RequestContext, data interface{}) {
    c.JSON(consts.StatusOK, map[string]interface{}{
        "code":    0,
        "message": "success",
        "data":    data,
    })
}

func Fail(c *app.RequestContext, code int, msg string) {
    c.JSON(consts.StatusOK, map[string]interface{}{
        "code":    code,
        "message": msg,
    })
}
```

---

## 5. 中间件使用

在 `biz/router/**/middleware.go` 中添加中间件（此文件为增量更新，安全修改）：

```go
// biz/router/report/service/middleware.go
package service

import (
    "github.com/cloudwego/hertz/pkg/app"
)

func ReportServiceMiddleware() []app.HandlerFunc {
    return []app.HandlerFunc{
        // 添加认证中间件
        authMiddleware(),
        // 添加日志中间件
        logMiddleware(),
    }
}

func authMiddleware() app.HandlerFunc {
    return func(ctx context.Context, c *app.RequestContext) {
        token := c.GetHeader("X-Token")
        if len(token) == 0 {
            c.AbortWithJSON(consts.StatusUnauthorized, map[string]interface{}{
                "code":    401,
                "message": "unauthorized",
            })
            return
        }
        c.Next(ctx)
    }
}
```

---

## 6. 添加新接口的完整流程

1. **修改 IDL**：在 `idl/report/service.thrift` 中添加新的 struct 和 service 方法。
2. **执行生成**：
   ```bash
   make hertz-update
   ```
3. **实现 Handler**：在 `biz/handler/report/report_service.go` 中找到新生成的方法框架并填写业务逻辑。
4. **验证路由**：检查 `biz/router/report/service/service.go` 中新路由是否正确注册。

---

## 7. 常见问题

| 问题 | 原因 | 解决方式 |
|------|------|----------|
| `make hertz-update` 后 handler 方法消失 | 修改了全量重新生成的文件 | 只在 `*_method.go` 里写业务代码 |
| 参数绑定失败（字段为零值） | IDL 字段注解写错或未加注解 | 检查 `api.body`/`api.query`/`api.path` 注解 |
| 路由 404 | namespace 路径与路由注册不一致 | 检查 `router_gen.go` 和 `register.go` |
| IDL 修改后生成报错 | thrift 语法错误 | 检查 struct 字段编号是否连续、括号是否闭合 |
| 客户端代码未更新 | 只运行了 `hertztool update` 未运行 `hertztool client` | 执行完整的 `make hertz-update` |
