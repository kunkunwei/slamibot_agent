# 项目：deployment（部署 / Docker）

> Docker 镜像、compose、部署脚本。默认禁止修改基础设施。

## 基本信息
- id: deployment
- name: 部署 / Docker
- repo: d360_nav2D / Jetson 板内部署工作树
- local_path: `/home/jetson/Scout_mini_navigation`
- lifecycle: CURRENT（配套 ROS1 基线）
- tech_stack: [docker]

## 允许修改范围（allowed_paths）
- 无全局默认写权限；每个部署任务必须明确镜像、容器、文件和回滚对象。

## 禁止修改范围 / 受保护基础设施
- Docker 基础设施结构（镜像、网络、daemon 配置、compose 顶层结构）
- 数据库结构
- rosbridge 接口
- 系统环境 / Jetson OS

## 开发流程
- 部署/重部署走 `procedures/jetson-validation.md`；DANGEROUS 操作永远人工确认。

## 事实源
- `facts/jetson_profile.yaml`
