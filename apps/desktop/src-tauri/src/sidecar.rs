//! sidecar 生命周期 + stdio NDJSON 中继（骨架）。
//!
//! 目标：Rust 拉起 Python 运行时（`--stdio`），把前端命令写入其 stdin，
//! 把其 stdout 上的事件转发为 Tauri 事件（`agent-event`）。运行时**不监听任何本地端口**。
//!
//! 开发期用 `uv run python -m demo_agent.server --stdio` 拉起；
//! 打包期替换为 bundled python-build-standalone 运行时（TODO，见 scripts/build-sidecar.sh）。

use std::io::{BufRead, BufReader, Write};
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;

use tauri::{AppHandle, Emitter, Manager};

/// 托管状态：持有 sidecar 子进程句柄，供命令写入 stdin。
pub struct SidecarState {
    child: Mutex<Option<Child>>,
}

impl SidecarState {
    fn new_with(child: Child) -> Self {
        Self {
            child: Mutex::new(Some(child)),
        }
    }

    /// 向 sidecar 的 stdin 写一行 NDJSON。
    fn send_line(&self, line: &str) -> Result<(), String> {
        let mut guard = self.child.lock().map_err(|e| e.to_string())?;
        let child = guard.as_mut().ok_or("sidecar 未运行")?;
        let stdin = child.stdin.as_mut().ok_or("sidecar stdin 不可用")?;
        stdin
            .write_all(line.as_bytes())
            .and_then(|_| stdin.write_all(b"\n"))
            .and_then(|_| stdin.flush())
            .map_err(|e| e.to_string())
    }
}

/// 构造 sidecar 启动命令（开发期走 uv）。
fn sidecar_command() -> (Command, PathBuf) {
    let mut cmd = Command::new("uv");
    cmd.args(["run", "python", "-m", "demo_agent.server", "--stdio"])
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());

    // 仓库根 = src-tauri 的上两级；开发期让 `uv run` 能找到 pyproject.toml。
    // 打包期 TODO：改为 bundled 运行时的可执行路径。
    let repo_root = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .and_then(|p| p.parent())
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from("."));

    (cmd, repo_root)
}

/// 拉起 sidecar 并启动 stdout / stderr 转发线程。
pub fn spawn(app: AppHandle) {
    let (mut command, cwd) = sidecar_command();
    let mut child = match command.current_dir(&cwd).spawn() {
        Ok(c) => c,
        Err(e) => {
            let _ = app.emit("agent-error", format!("sidecar 启动失败: {e}"));
            return;
        }
    };

    // stdout → agent-event（NDJSON 事件流）
    if let Some(stdout) = child.stdout.take() {
        let app = app.clone();
        std::thread::spawn(move || {
            for line in BufReader::new(stdout).lines().map_while(Result::ok) {
                let ev: serde_json::Value = match serde_json::from_str(&line) {
                    Ok(v) => v,
                    Err(_) => continue,
                };
                let _ = app.emit("agent-event", ev);
            }
            let _ = app.emit("agent-exit", ());
        });
    }

    // stderr → agent-stderr（开发期便于排查）
    if let Some(stderr) = child.stderr.take() {
        let app = app.clone();
        std::thread::spawn(move || {
            for line in BufReader::new(stderr).lines().map_while(Result::ok) {
                let _ = app.emit("agent-stderr", line);
            }
        });
    }

    app.manage(SidecarState::new_with(child));
}

/// 向前端命令入口：把 JSON 命令写进 sidecar stdin。
pub fn send(app: &AppHandle, msg: serde_json::Value) -> Result<(), String> {
    let state = app.state::<SidecarState>();
    state.send_line(&serde_json::to_string(&msg).map_err(|e| e.to_string())?)
}
