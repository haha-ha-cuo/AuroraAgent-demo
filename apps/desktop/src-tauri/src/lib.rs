mod sidecar;

/// 健康检查。
#[tauri::command]
fn ping() -> &'static str {
    "pong"
}

/// 前端 → 运行时：发起一次任务（经 stdio 中继写入 sidecar stdin）。
#[tauri::command]
fn agent_run(app: tauri::AppHandle, objective: String) -> Result<(), String> {
    sidecar::send(&app, serde_json::json!({ "type": "run", "objective": objective }))
}

/// 前端 → 运行时：确认门回复。
#[tauri::command]
fn agent_confirm(app: tauri::AppHandle, request_id: String, approved: bool) -> Result<(), String> {
    sidecar::send(
        &app,
        serde_json::json!({ "type": "confirm", "request_id": request_id, "approved": approved }),
    )
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .setup(|app| {
            sidecar::spawn(app.handle().clone());
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![ping, agent_run, agent_confirm])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
