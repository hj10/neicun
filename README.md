# 内存释放专家（示例版）

一个模仿经典“内存整理工具”风格的桌面程序，使用 Python + Tkinter 实现。

## 这次重点修复/新增

- 保持原始桌面功能不变：默认启动仍是 GUI（设置/定时释放/立即释放/退出）。
- 新增**后台模式**：可无界面定时执行内存整理。
- 新增**保活模式**：后台进程退出后自动重启。
- 保留桌面 UI 模式，并在“优化规则”页补充运行方式说明。
- 调度继续使用 Tk `after`（UI 模式）以避免线程调度风险。

## 功能

- 基本设置页（开机自启开关、定时释放内存、间隔分钟数）
- 定时自动执行内存释放
- 手动“立即释放”
- 显示总内存、已用内存、可用比例
- 本地保存配置（`~/.memory_manager/config.json`）
- 后台运行与保活运行

## 运行环境

- Python 3.10+
- `psutil`
- Tkinter（大多数 Python 发行版自带）

## 安装依赖

```bash
pip install -r requirements.txt
```

## 启动方式

### 1) 桌面模式

```bash
python memory_manager.py
```

### 2) 后台模式（无界面）

```bash
python memory_manager.py --background
```

### 3) 保活模式（监控后台进程）

```bash
python memory_manager.py --keepalive
```

### 4) 后台单次执行（测试）

```bash
python memory_manager.py --background --once
```

## 日志

后台模式日志输出到：

- `~/.memory_manager/background.log`

## 说明

- 该项目是教学/演示用途。
- 现代操作系统本身具有成熟的内存管理机制，“释放内存”通常只会触发垃圾回收和工作集整理，不会替代硬件升级。
