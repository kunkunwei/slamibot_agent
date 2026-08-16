# 知识：Jetson（远程目标）

## 用途
记录 Jetson Orin NX 的远程开发、编译、测试、运行、踩坑。

## 事实源
- `facts/jetson_profile.yaml`（SSH、OS、ROS、Docker、workspace、权限分级）

## 关键约束
- Jetson 只作为远程目标；禁止向其新增 Agent/RAG/向量库/AI 服务/后台进程/额外容器。
- 权限四级：READ_ONLY（默认）/ BUILD / DEPLOY / DANGEROUS（永远人工确认）。

## 索引
<!-- 例如：
- [Jetson-网络与端口.md](./Jetson-网络与端口.md)
-->
（暂无，待回填。）
