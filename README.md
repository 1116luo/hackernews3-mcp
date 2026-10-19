# hackernews3-mcp

一个基于 Python 的 [Hacker News](https://news.ycombinator.com/) MCP（Model Context Protocol）服务，让 AI 助手能够查询 HN 资讯、搜索内容、查看用户与评论。

## 功能

| 工具 | 说明 |
| --- | --- |
| `get_top_stories` | 首页热门故事 |
| `get_new_stories` | 最新故事 |
| `get_best_stories` | 高分故事 |
| `get_ask_stories` | Ask HN 提问 |
| `get_show_stories` | Show HN 作品展示 |
| `get_job_stories` | 招聘信息 |
| `get_item` | 按 ID 获取单条内容 |
| `search_stories` | 全文搜索（Algolia） |
| `get_user` | 用户信息 |
| `get_story_with_comments` | 故事 + 热门评论 |

数据来源：

- Firebase API：`https://hacker-news.firebaseio.com/v0`
- Algolia 搜索：`https://hn.algolia.com/api/v1`

## 环境要求

- Python 3.10+
- 依赖见 `requirements.txt`

## 安装

```bash
pip install -r requirements.txt
```

## 运行

```bash
python server.py
```

默认使用 stdio 传输。

## 配置到 MCP 客户端

以 Claude Desktop / CodeBuddy 等客户端为例，添加如下配置：

```json
{
  "mcpServers": {
    "hackernews3-mcp": {
      "command": "python",
      "args": ["/绝对路径/server.py"]
    }
  }
}
```

如果使用 `mcp` 命令行工具本地调试：

```bash
mcp dev server.py
```

## License

MIT
