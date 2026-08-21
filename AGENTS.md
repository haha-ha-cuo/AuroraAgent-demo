# 项目目标实现

项目意在制作一个形如codeX那样可以全平台发放的ai agent桌面应用

# 项目初步预设技术栈

- langchaim
- kvchache
- langgraph
- mcp

# 项目构想

agent在拿到项目之后会将任务委派给子agent，由agent自身决定agent调用质量（例如codeX中的推理强度）。同时在kvchache层对外开放一些接口，用于用户自生决定去特化agent哪些能力。委派任务应该是个树形图。

# 项目管理

python环境请务必用uv进行管理。
