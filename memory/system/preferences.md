# System Preferences

## Memory Search Configuration

### Recommended Settings
```json
{
  "memorySearch": {
    "enabled": true,
    "provider": "local",
    "sources": ["memory", "sessions"],
    "indexMode": "hot",
    "minScore": 0.3,
    "maxResults": 20
  }
}
```

### Provider Selection
- **local**: 无需 API key，使用本地嵌入模型
- **voyage**: 需要 VOYAGE_API_KEY（推荐，质量更高）
- **openai**: 需要 OPENAI_API_KEY

## Setup Notes
- 使用 local provider 无需额外配置
- 如需更高质量的记忆搜索，可申请 Voyage API key
- 记忆搜索在每次心跳时自动索引新内容

## Files Structure
```
workspace/
├── MEMORY.md              # 长期记忆（已配置）
└── memory/
    ├── logs/              # 每日日志（已配置）
    ├── projects/          # 项目特定记忆
    ├── groups/            # 群组聊天记忆
    └── system/            # 系统配置（当前文件）
```

## Active Projects
1. Alpha-Genesis V6.0 量化交易系统
2. OpenClaw 技能开发

## User Communication Style
- 直接、高效
- 偏好行动而非冗长解释
- 技术背景强，不需要基础概念解释
