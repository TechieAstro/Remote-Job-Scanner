# PowerShell script to register the Remote Job Scanner in Windows Task Scheduler
# Run this script as Administrator (or standard user with task scheduling permissions)

$TaskName = "RemoteJobScanner"
$PythonPath = "C:\Users\Administrator\AppData\Local\Microsoft\WindowsApps\PythonSoftwareFoundation.Python.3.13_qbz5n2kfra8p0\python.exe"
$ScriptPath = "C:\Users\Administrator\remote-job-scanner\scanner.py"
$WorkDir = "C:\Users\Administrator\remote-job-scanner"

Write-Host "Scheduling Remote Job Scanner task..."

# Check if Python executable exists
if (-not (Test-Path $PythonPath)) {
    Write-Warning "Python path $PythonPath not found. Attempting to fall back to general 'python.exe'..."
    $PythonPath = "python.exe"
}

# Create Scheduled Task Action
$Action = New-ScheduledTaskAction -Execute $PythonPath -Argument $ScriptPath -WorkingDirectory $WorkDir

# Create Scheduled Task Trigger: Run immediately once, repeat hourly, indefinitely
$Trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Hours 1)

# Configure Settings: Allow run on batteries, start when available, run in parallel if overlap
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -MultipleInstances Parallel

# Register Task
Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Description "Scans remote job boards hourly for Cybersecurity, Virtual Assistant, and IT Support positions." -Force

Write-Host "Scheduled task '$TaskName' successfully registered!"
Write-Host "You can test-run it immediately by running: Start-ScheduledTask -TaskName '$TaskName'"
Write-Host "You can monitor or remove it using Windows Task Scheduler (taskschd.msc)."
