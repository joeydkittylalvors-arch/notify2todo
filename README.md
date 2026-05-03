# notify2todo

自动从 QQ邮箱、学习通（超星）提取通知，生成手机待办日历。

## 功能

- **QQ邮箱**：IMAP 关键词匹配，自动提取图书馆到期/取书通知、课程通知等
- **学习通**：通过 ADB + uiautomator 从 MuMu 模拟器读取收件箱（绕过反爬）
- **去重过滤**：SQLite 记录已处理通知，避免重复；时间过滤去除过期/太远的条目
- **ICS 日历**：生成标准 ICS 文件，邮件发送到手机，一键导入日历
- **定时自动化**：Windows 任务计划程序，开机自动运行

## 架构

```
QQ邮箱(IMAP) ──→ 关键词匹配 ──→
                              ├→ 去重过滤 → ICS生成 → 邮件发送 → 手机导入
学习通(ADB UI提取) ──→ 消息解析 ──→
```

## 依赖

- Python 3.12+
- MuMu 模拟器（用于学习通）
- QQ邮箱 IMAP/SMTP 授权码

```
pip install -r requirements.txt
```

## 配置

复制 `config.example.yaml` 为 `config.yaml`，填写：

```yaml
qqmail:
  email: "your@qq.com"
  auth_code: "QQ邮箱授权码"

chaoxing:
  username: "学号"
  password: "密码"
  school_name: "学校名称"
```

## 使用

```bash
# 手动运行
python main.py

# 或双击 run_auto.bat（自动启动MuMu → 打开学习通 → 扫描）

# 注册开机自动运行
scripts\setup_task.ps1
```

## 项目结构

```
src/
├── qqmail_fetcher.py    # QQ邮箱 IMAP 抓取
├── chaoxing_fetcher.py  # 学习通 ADB UI 提取
├── todo_merger.py       # 去重+时间过滤
├── ics_exporter.py      # ICS 日历生成
├── mail_sender.py       # SMTP 邮件发送
├── db_manager.py        # SQLite 管理
├── config_loader.py     # 配置加载
└── logger.py            # 日志
main.py                   # 主入口
run_auto.bat / run_auto.ps1  # 自动化启动脚本
```

## License

MIT
