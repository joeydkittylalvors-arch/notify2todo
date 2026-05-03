$ErrorActionPreference = "Continue"
Set-Location C:\Users\Lenovo\notify2todo

Write-Host "============================================"
Write-Host "  notify2todo auto"
Write-Host "============================================"
Write-Host ""

# 1. Start MuMu
Write-Host "[1/5] Check MuMu..."
$mumu = Get-Process -Name "MuMuNxMain" -ErrorAction SilentlyContinue
if (-not $mumu) {
    Write-Host "  Starting MuMu..."
    Start-Process "C:\Program Files\Netease\MuMu\nx_main\MuMuNxMain.exe"
    Write-Host "  Waiting 30s..."
    Start-Sleep 30
} else {
    Write-Host "  MuMu already running"
}

# 2. ADB
Write-Host ""
Write-Host "[2/5] Connect ADB..."
$ADB = "C:\Program Files\Netease\MuMu\nx_device\12.0\shell\adb.exe"
& $ADB connect 127.0.0.1:7555 2>$null
$ok = & $ADB -s 127.0.0.1:7555 shell echo ok 2>$null
if ($ok -notmatch "ok") {
    Write-Host "  ADB failed, retry..."
    Start-Sleep 5
    & $ADB connect 127.0.0.1:7555 2>$null
}

# 3. Launch learning通
Write-Host ""
Write-Host "[3/5] Launch learning通..."
& $ADB -s 127.0.0.1:7555 shell monkey -p com.chaoxing.mobile -c android.intent.category.LAUNCHER 1 2>$null
Write-Host "  Waiting 8s..."
Start-Sleep 8

# 4. Navigate to inbox
Write-Host ""
Write-Host "[4/5] Navigate to inbox..."
& $ADB -s 127.0.0.1:7555 shell input tap 400 1850 2>$null
Start-Sleep 2

# 5. Run main
Write-Host ""
Write-Host "[5/5] Scanning..."
python main.py

Write-Host ""
Write-Host "============================================"
Write-Host "  Done! Check phone for ICS email"
Write-Host "============================================"
