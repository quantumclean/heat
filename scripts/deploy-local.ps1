# HEAT Local Deploy Script
# Deploy directly from your machine to S3

param(
    [Parameter(Mandatory=$true)]
    [string]$BucketName,
    
    [switch]$SkipPipeline
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)

Write-Host "=== HEAT Local Deploy ===" -ForegroundColor Cyan
Write-Host "Bucket: $BucketName" -ForegroundColor Gray

# Run pipeline unless skipped
if (!$SkipPipeline) {
    Write-Host "`n[1/9] Running RSS Scraper..." -ForegroundColor Yellow
    python "$projectRoot\processing\rss_scraper.py"
    
    Write-Host "`n[2/9] Running Ingestion..." -ForegroundColor Yellow
    python "$projectRoot\processing\ingest.py"
    
    Write-Host "`n[3/9] Running Clustering..." -ForegroundColor Yellow
    python "$projectRoot\processing\cluster.py"
    
    Write-Host "`n[4/9] Running NLP Analysis..." -ForegroundColor Yellow
    python "$projectRoot\processing\nlp_analysis.py"
    
    Write-Host "`n[5/9] Running Buffer..." -ForegroundColor Yellow
    python "$projectRoot\processing\buffer.py"
    
    Write-Host "`n[6/9] Exporting Static Files..." -ForegroundColor Yellow
    python "$projectRoot\processing\export_static.py"
    
    Write-Host "`n[7/9] Generating Alerts..." -ForegroundColor Yellow
    python "$projectRoot\processing\alerts.py"
    
    Write-Host "`n[8/9] Generating Tiered Exports..." -ForegroundColor Yellow
    python "$projectRoot\processing\tiers.py"
}

Write-Host "`n[9/9] Syncing to S3..." -ForegroundColor Yellow
aws s3 sync "$projectRoot\build" "s3://$BucketName/" `
    --delete `
    --cache-control "max-age=300" `
    --exclude "*.map"

Write-Host "`n=== Deploy Complete ===" -ForegroundColor Green
Write-Host "Site URL: http://$BucketName.s3-website-us-east-1.amazonaws.com" -ForegroundColor Cyan
