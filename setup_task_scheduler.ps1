# Windows Task Scheduler Setup for They Are Here
# Automates data collection at optimal intervals with zero cost
#
# Usage: Run in PowerShell as Administrator
#   .\setup_task_scheduler.ps1
#
# This script creates scheduled tasks for all scrapers at optimal frequencies.

$ErrorActionPreference = "Stop"

# ============================================================================
# Configuration
# ============================================================================

$ProjectDir = "C:\Programming\heat"
$VenvPython = "C:\Programming\.venv\Scripts\python.exe"
$LogDir = "$ProjectDir\logs"

# Create logs directory if it doesn't exist
if (!(Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir | Out-Null
    Write-Host "Created logs directory: $LogDir"
}

# ============================================================================
# Helper Function to Create Scheduled Task
# ============================================================================

function New-HeatScheduledTask {
    param(
        [string]$TaskName,
        [string]$Description,
        [string]$ScriptName,
        [string]$TriggerType,  # "Hourly", "Daily", "Weekly", "Interval"
        [int]$Interval = 0,     # For interval triggers (hours)
        [int]$Hour = 9,         # For daily/weekly triggers
        [int]$Minute = 0,       # For daily/weekly triggers
        [string]$DayOfWeek = "" # For weekly triggers (e.g., "Monday")
    )

    # Build command
    $ScriptPath = "$ProjectDir\processing\$ScriptName"
    $LogFile = "$LogDir\$($TaskName).log"
    $Command = "$VenvPython `"$ScriptPath`" >> `"$LogFile`" 2>&1"

    # Create trigger based on type
    $TriggerArgs = @{}

    switch ($TriggerType) {
        "Hourly" {
            $Trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Hours $Interval)
        }
        "Daily" {
            $TimeString = "{0:D2}:{1:D2}" -f $Hour, $Minute
            $Trigger = New-ScheduledTaskTrigger -Daily -At $TimeString
        }
        "Weekly" {
            $TimeString = "{0:D2}:{1:D2}" -f $Hour, $Minute
            $Trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $DayOfWeek -At $TimeString
        }
    }

    # Create action
    $Action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -WindowStyle Hidden -Command `"$Command`""

    # Create settings
    $Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

    # Register task
    try {
        # Remove existing task if it exists
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

        # Register new task
        Register-ScheduledTask -TaskName $TaskName -Description $Description -Trigger $Trigger -Action $Action -Settings $Settings -Force | Out-Null

        Write-Host "[OK] Created task: $TaskName" -ForegroundColor Green
    }
    catch {
        Write-Host "[ERROR] Failed to create task: $TaskName" -ForegroundColor Red
        Write-Host "  Error: $_" -ForegroundColor Red
    }
}

# ============================================================================
# Create Scheduled Tasks
# ============================================================================

Write-Host ""
Write-Host "=" * 60
Write-Host "They Are Here - Task Scheduler Setup"
Write-Host "=" * 60
Write-Host ""

# Check if running as Administrator
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (!$isAdmin) {
    Write-Host "[WARNING] Not running as Administrator" -ForegroundColor Yellow
    Write-Host "  Some features may not work correctly." -ForegroundColor Yellow
    Write-Host "  Run PowerShell as Administrator for best results." -ForegroundColor Yellow
    Write-Host ""
}

# Check if virtual environment exists
if (!(Test-Path $VenvPython)) {
    Write-Host "[ERROR] Virtual environment not found at: $VenvPython" -ForegroundColor Red
    Write-Host "  Please update `$VenvPython in this script." -ForegroundColor Red
    exit 1
}

Write-Host "Configuration:"
Write-Host "  Project Dir: $ProjectDir"
Write-Host "  Python: $VenvPython"
Write-Host "  Logs: $LogDir"
Write-Host ""

Write-Host "Creating scheduled tasks..."
Write-Host ""

# ===== High-Frequency Tasks =====

Write-Host "High-Frequency Tasks:" -ForegroundColor Cyan

# Every 1 hour: Google News
New-HeatScheduledTask `
    -TaskName "HEAT-GoogleNews-Hourly" `
    -Description "Scrape Google News RSS every hour" `
    -ScriptName "scraper.py" `
    -TriggerType "Hourly" `
    -Interval 1

# Every 4 hours: Local News RSS
New-HeatScheduledTask `
    -TaskName "HEAT-LocalNews-4Hours" `
    -Description "Scrape local news RSS every 4 hours" `
    -ScriptName "rss_scraper.py" `
    -TriggerType "Hourly" `
    -Interval 4

# Every 4 hours: Reddit
New-HeatScheduledTask `
    -TaskName "HEAT-Reddit-4Hours" `
    -Description "Scrape Reddit community discussions every 4 hours" `
    -ScriptName "reddit_scraper.py" `
    -TriggerType "Hourly" `
    -Interval 4

# Every 6 hours: FEMA IPAWS
New-HeatScheduledTask `
    -TaskName "HEAT-FEMA-6Hours" `
    -Description "Scrape FEMA IPAWS alerts every 6 hours" `
    -ScriptName "fema_ipaws_scraper.py" `
    -TriggerType "Hourly" `
    -Interval 6

Write-Host ""

# ===== Daily Tasks =====

Write-Host "Daily Tasks:" -ForegroundColor Cyan

# Daily at 9:00 AM: NJ Attorney General
New-HeatScheduledTask `
    -TaskName "HEAT-NJAG-Daily" `
    -Description "Scrape NJ AG press releases daily at 9 AM" `
    -ScriptName "nj_ag_scraper.py" `
    -TriggerType "Daily" `
    -Hour 9 `
    -Minute 0

# Daily at 8:00 AM: Facebook
New-HeatScheduledTask `
    -TaskName "HEAT-Facebook-Daily" `
    -Description "Scrape Facebook events daily at 8 AM" `
    -ScriptName "facebook_scraper.py" `
    -TriggerType "Daily" `
    -Hour 8 `
    -Minute 0

Write-Host ""

# ===== Weekly Tasks =====

Write-Host "Weekly Tasks:" -ForegroundColor Cyan

# Weekly on Monday at 10:00 AM: Council Minutes
New-HeatScheduledTask `
    -TaskName "HEAT-CouncilMinutes-Weekly" `
    -Description "Scrape city council minutes weekly on Monday at 10 AM" `
    -ScriptName "council_minutes_scraper.py" `
    -TriggerType "Weekly" `
    -DayOfWeek "Monday" `
    -Hour 10 `
    -Minute 0

Write-Host ""

# ===== Processing Pipeline Task =====

Write-Host "Processing Pipeline:" -ForegroundColor Cyan

# Create a task for the full processing pipeline (runs after each scraper)
# Note: This should be triggered manually or by the scrapers themselves
New-HeatScheduledTask `
    -TaskName "HEAT-ProcessPipeline" `
    -Description "Process scraped data through full pipeline" `
    -ScriptName "..\run_pipeline.py" `
    -TriggerType "Daily" `
    -Hour 23 `
    -Minute 30

Write-Host ""
Write-Host "=" * 60
Write-Host "Setup Complete!"
Write-Host "=" * 60
Write-Host ""

Write-Host "Scheduled Tasks Created:" -ForegroundColor Green
Write-Host "  - HEAT-GoogleNews-Hourly (every 1 hour)"
Write-Host "  - HEAT-LocalNews-4Hours (every 4 hours)"
Write-Host "  - HEAT-Reddit-4Hours (every 4 hours)"
Write-Host "  - HEAT-FEMA-6Hours (every 6 hours)"
Write-Host "  - HEAT-NJAG-Daily (daily at 9 AM)"
Write-Host "  - HEAT-Facebook-Daily (daily at 8 AM)"
Write-Host "  - HEAT-CouncilMinutes-Weekly (Monday at 10 AM)"
Write-Host "  - HEAT-ProcessPipeline (daily at 11:30 PM)"
Write-Host ""

Write-Host "Important Notes:" -ForegroundColor Yellow
Write-Host "  1. Reddit scraper requires REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET"
Write-Host "     environment variables. Set them before running the task."
Write-Host ""
Write-Host "  2. Logs will be saved to: $LogDir"
Write-Host ""
Write-Host "  3. To view tasks: taskschd.msc"
Write-Host ""
Write-Host "  4. To remove all tasks, run:"
Write-Host "     Get-ScheduledTask -TaskName 'HEAT-*' | Unregister-ScheduledTask -Confirm:`$false"
Write-Host ""
Write-Host "  5. Each scraper runs independently. The processing pipeline"
Write-Host "     runs once per day to process all collected data."
Write-Host ""

Write-Host "Next Steps:" -ForegroundColor Cyan
Write-Host "  1. Get Reddit API credentials (5 minutes):"
Write-Host "     https://www.reddit.com/prefs/apps"
Write-Host ""
Write-Host "  2. Set environment variables (system-wide):"
Write-Host "     [System.Environment]::SetEnvironmentVariable('REDDIT_CLIENT_ID', 'your_id', 'User')"
Write-Host "     [System.Environment]::SetEnvironmentVariable('REDDIT_CLIENT_SECRET', 'your_secret', 'User')"
Write-Host ""
Write-Host "  3. Test a task manually:"
Write-Host "     Start-ScheduledTask -TaskName 'HEAT-NJAG-Daily'"
Write-Host ""

Write-Host "All tasks are now scheduled and will run automatically!" -ForegroundColor Green
Write-Host ""
