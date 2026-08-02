# CHANGELOG - B站UP主视频监控服务

所有用户可感知的变更记录。

---

## 2026-08-02 — 项目初始化

**新增**
- 项目代码框架：main.py 入口 + src 模块结构
- 配置管理：config/settings.yaml + YAML加载逻辑
- B站登录模块骨架：扫码登录接口定义
- B站API模块骨架：关注列表、视频列表接口定义
- 飞书推送模块骨架：Webhook推送接口定义
- 定时调度模块骨架：监控循环逻辑框架
- systemd服务配置：bilibili-monitor.service
- 项目文档：README.md + PRD

**待办**
- 实现扫码登录逻辑
- 实现B站API调用
- 实现飞书推送
- 实现定时调度
- 服务器部署测试