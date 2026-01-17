# HEAT S3 Setup Script
# Run this once to create the S3 bucket and configure static hosting

param(
    [Parameter(Mandatory=$true)]
    [string]$BucketName,
    
    [string]$Region = "us-east-1"
)

Write-Host "=== HEAT S3 Setup ===" -ForegroundColor Cyan

# Check AWS CLI
if (!(Get-Command aws -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: AWS CLI not found. Install from https://aws.amazon.com/cli/" -ForegroundColor Red
    exit 1
}

# Create bucket
Write-Host "`nCreating S3 bucket: $BucketName" -ForegroundColor Yellow
aws s3 mb "s3://$BucketName" --region $Region

# Disable block public access
Write-Host "Configuring public access..." -ForegroundColor Yellow
aws s3api put-public-access-block `
    --bucket $BucketName `
    --public-access-block-configuration "BlockPublicAcls=false,IgnorePublicAcls=false,BlockPublicPolicy=false,RestrictPublicBuckets=false"

# Create bucket policy for public read
$policy = @"
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "PublicReadGetObject",
            "Effect": "Allow",
            "Principal": "*",
            "Action": "s3:GetObject",
            "Resource": "arn:aws:s3:::$BucketName/*"
        }
    ]
}
"@

Write-Host "Applying bucket policy..." -ForegroundColor Yellow
$policy | Out-File -FilePath "temp-policy.json" -Encoding UTF8
aws s3api put-bucket-policy --bucket $BucketName --policy file://temp-policy.json
Remove-Item "temp-policy.json"

# Enable static website hosting
Write-Host "Enabling static website hosting..." -ForegroundColor Yellow
aws s3 website "s3://$BucketName" --index-document index.html --error-document index.html

# Get website URL
$websiteUrl = "http://$BucketName.s3-website-$Region.amazonaws.com"

Write-Host "`n=== Setup Complete ===" -ForegroundColor Green
Write-Host "Bucket: $BucketName" -ForegroundColor White
Write-Host "Website URL: $websiteUrl" -ForegroundColor Cyan
Write-Host "`nNext steps:" -ForegroundColor Yellow
Write-Host "1. Add these secrets to GitHub repo:" -ForegroundColor White
Write-Host "   - AWS_ACCESS_KEY_ID" -ForegroundColor Gray
Write-Host "   - AWS_SECRET_ACCESS_KEY" -ForegroundColor Gray
Write-Host "   - S3_BUCKET_NAME = $BucketName" -ForegroundColor Gray
Write-Host "2. Push to main branch to trigger deploy" -ForegroundColor White
Write-Host "3. (Optional) Add CloudFront for HTTPS + CDN" -ForegroundColor White
