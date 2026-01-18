@echo off
REM HEAT - Deploy to AWS S3
REM Syncs the build folder to S3 static website hosting

echo ========================================
echo HEAT S3 Deployment
echo ========================================
echo.

REM --- CONFIGURATION ---
REM Change this to your bucket name
set BUCKET_NAME=heat-plainfield
set REGION=us-east-1
set CLOUDFRONT_ID=E7LJPCZOG4PM9

cd /d "%~dp0.."

echo Deploying to S3 bucket: %BUCKET_NAME%
echo.

REM Sync build folder to S3
aws s3 sync build/ s3://%BUCKET_NAME%/ ^
    --delete ^
    --cache-control "max-age=3600" ^
    --exclude ".DS_Store" ^
    --exclude "*.map"

if %ERRORLEVEL% NEQ 0 (
    echo ERROR: S3 sync failed!
    echo.
    echo Make sure:
    echo   1. AWS CLI is installed
    echo   2. You have run 'aws configure'
    echo   3. The bucket name is correct
    pause
    exit /b 1
)

echo.
echo S3 sync complete! Invalidating CloudFront cache...
echo.

REM Invalidate CloudFront cache
aws cloudfront create-invalidation ^
    --distribution-id %CLOUDFRONT_ID% ^
    --paths "/*"

if %ERRORLEVEL% NEQ 0 (
    echo WARNING: CloudFront invalidation failed!
    echo Deployment succeeded but cache may not be updated immediately.
    echo.
) else (
    echo CloudFront cache invalidated successfully!
    echo.
)

echo.
echo ========================================
echo Deployment complete!
echo.
echo Your site is available at:
echo https://d18kxgbrvjlp8x.cloudfront.net
echo ========================================
pause
