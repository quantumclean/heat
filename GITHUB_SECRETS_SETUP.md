# GitHub Secrets Setup for HEAT

## Required Secrets

Go to: **https://github.com/quantumclean/heat/settings/secrets/actions**

Click **"New repository secret"** and add each of these:

---

### 1. S3_BUCKET_NAME
- **Name:** `S3_BUCKET_NAME`
- **Value:** `heat-plainfield`
- **Status:** ✅ (Confirmed from workflow error)

---

### 2. AWS_ACCESS_KEY_ID
- **Name:** `AWS_ACCESS_KEY_ID`
- **Value:** Your AWS access key (starts with `AKIA...`)
- **Where to find:**
  - Check `%USERPROFILE%\.aws\credentials` file
  - OR: AWS Console → IAM → Users → heat-deploy → Security credentials → Access keys

---

### 3. AWS_SECRET_ACCESS_KEY
- **Name:** `AWS_SECRET_ACCESS_KEY`
- **Value:** Your AWS secret access key (long alphanumeric string)
- **Where to find:** Same location as access key ID above

---

### 4. CLOUDFRONT_DISTRIBUTION_ID (Optional)
- **Name:** `CLOUDFRONT_DISTRIBUTION_ID`
- **Value:** `D18KXGBRVJLP8X`
- **Note:** CloudFront invalidation will fail gracefully if IAM permissions not set

---

## Current Status

✅ **Workflow syntax:** Fixed (commit 6faa7d4)  
✅ **CloudFront ID:** Found (`D18KXGBRVJLP8X`)  
✅ **IAM User:** `heat-deploy` (Account: 120569637265)  
⚠️ **GitHub Secrets:** Need to be added manually via GitHub Settings  
⚠️ **CloudFront Permissions:** Optional - workflow will continue without them

---

## After Adding Secrets

1. Go to: https://github.com/quantumclean/heat/actions
2. Click on "Deploy HEAT to S3" workflow
3. Click "Run workflow" button
4. Monitor the deployment progress

---

## Troubleshooting

**If workflow still fails after adding secrets:**
- Verify secret names match exactly (case-sensitive)
- Check AWS credentials are for `heat-deploy` user
- Ensure S3 bucket `heat-plainfield` exists and has public access enabled

**To test deployment locally:**
```powershell
cd "C:\Users\villa\OneDrive\Desktop\Programming\heat"
.\scripts\run_pipeline.bat
aws s3 sync build/ s3://heat-plainfield/ --acl public-read --delete
```

**Your CloudFront URL:**
- Distribution ID: D18KXGBRVJLP8X
- Find URL at: AWS Console → CloudFront → Distributions → D18KXGBRVJLP8X → Domain name
