# Superpowers Skills for Trae

Superpowers是一个完整的AI编程方法论系统，已安装到本项目中。

## 已安装的Skills

以下skills已安装在 `g:\touzi-agent\.trae\skills\superpowers\` 目录：

### 核心工作流Skills
- **brainstorming** - 头脑风暴与设计细化
- **writing-plans** - 编写详细实施计划
- **executing-plans** - 执行计划（带检查点）
- **subagent-driven-development** - 子代理驱动开发（两阶段审查）
- **test-driven-development** - 测试驱动开发（RED-GREEN-REFACTOR循环）
- **systematic-debugging** - 系统化调试（4阶段根因分析）
- **verification-before-completion** - 完成前验证

### 协作Skills
- **requesting-code-review** - 请求代码审查
- **receiving-code-review** - 接收代码审查反馈
- **using-git-worktrees** - 使用Git工作树进行并行开发
- **finishing-a-development-branch** - 完成开发分支（合并/PR决策）
- **dispatching-parallel-agents** - 并行代理调度

### Meta Skills
- **writing-skills** - 创建新skills的最佳实践
- **using-superpowers** - Superpowers系统介绍

## 如何使用

### 方法1：直接调用Skill（推荐）
在对话中，你可以直接请求使用某个skill：

```
请使用 brainstorming skill 来帮我设计这个功能
```

```
使用 test-driven-development skill 来实现这个模块
```

```
用 systematic-debugging skill 来诊断这个bug
```

### 方法2：自动触发
Superpowers skills会根据你的任务自动触发。例如：
- 当你开始新功能开发时，brainstorming会自动激活
- 当你写代码时，TDD skill会引导你先写测试
- 当你遇到bug时，systematic-debugging会引导你系统化分析

## 核心方法论

Superpowers遵循以下核心原则：

1. **测试驱动开发** - 先写测试，总是如此
2. **系统化优于临时性** - 流程优于猜测
3. **复杂性降低** - 简洁性为主要目标
4. **证据优于声明** - 验证后再宣布成功

## 工作流程

典型开发流程：

1. **brainstorming** → 激活并细化想法，生成设计文档
2. **using-git-worktrees** → 创建隔离工作空间
3. **writing-plans** → 分解为小任务（每个2-5分钟）
4. **subagent-driven-development** → 逐任务执行，两阶段审查
5. **test-driven-development** → RED-GREEN-REFACTOR循环
6. **requesting-code-review** → 任务间审查
7. **finishing-a-development-branch** → 合并/PR决策

## 更新

要更新Superpowers到最新版本：

```powershell
git clone https://github.com/obra/superpowers.git C:\Users\Administrator\.trae-cn\superpowers-temp
Copy-Item -Recurse -Force "C:\Users\Administrator\.trae-cn\superpowers-temp\skills\*" "g:\touzi-agent\.trae\skills\superpowers\"
Remove-Item -Recurse -Force "C:\Users\Administrator\.trae-cn\superpowers-temp"
```

## 更多信息

- GitHub: https://github.com/obra/superpowers
- Discord: https://discord.gg/35wsABTejz
- 发布公告: https://blog.fsck.com/2025/10/09/superpowers/

## 许可证

MIT License