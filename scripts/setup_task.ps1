$taskName = "notify2todo"
$scriptPath = "C:\Users\Lenovo\notify2todo\run_auto.ps1"
$pythonPath = (Get-Command python).Source

# Delete old task
schtasks /Delete /TN $taskName /F 2>$null

# Create new task: daily at 9am
schtasks /Create /TN $taskName `
  /TR "powershell -ExecutionPolicy Bypass -File `"$scriptPath`"" `
  /SC DAILY `
  /ST 09:00 `
  /F `
  /RL HIGHEST

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "Task '$taskName' registered! Runs daily at 9:00 AM"
    Write-Host ""
    Write-Host "Check in Task Scheduler: taskschd.msc"
} else {
    Write-Host "Failed! Right-click this script and run as Administrator"
}
pause
