@echo off
REM HEAT - One-time S3 bucket setup
REM Run this once to create and configure your S3 bucket

echo ========================================
echo HEAT S3 Bucket Setup
echo ========================================
echo.

REM --- CONFIGURATION ---
set BUCKET_NAME=your-heat-map-bucket
set REGION=us-east-1

echo This script will:
echo   1. Create S3 bucket: %BUCKET_NAME%
echo   2. Enable static website hosting
echo   3. Set public read access
echo.
echo Press Ctrl+C to cancel, or
pause

echo.
echo [1/4] Creating bucket...
aws s3 mb s3://%BUCKET_NAME% --region %REGION%

echo.
echo [2/4] Enabling static website hosting...
aws s3 website s3://%BUCKET_NAME%/ --index-document index.html --error-document index.html

echo.
echo [3/4] Disabling block public access...
aws s3api put-public-access-block ^
    --bucket %BUCKET_NAME% ^
    --public-access-block-configuration "BlockPublicAcls=false,IgnorePublicAcls=false,BlockPublicPolicy=false,RestrictPublicBuckets=false"

echo.
echo [4/4] Setting bucket policy for public read...
echo {"Version":"2012-10-17","Statement":[{"Sid":"PublicReadGetObject","Effect":"Allow","Principal":"*","Action":"s3:GetObject","Resource":"arn:aws:s3:::%BUCKET_NAME%/*"}]} > bucket-policy.json
aws s3api put-bucket-policy --bucket %BUCKET_NAME% --policy file://bucket-policy.json
del bucket-policy.json

echo.
echo ========================================
echo Setup complete!
echo.
echo Your bucket is ready at:
echo http://%BUCKET_NAME%.s3-website-%REGION%.amazonaws.com
echo.
echo Now run: scripts\run_pipeline.bat
echo Then run: scripts\deploy_s3.bat
echo ========================================
pause
