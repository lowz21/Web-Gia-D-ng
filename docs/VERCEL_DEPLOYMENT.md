# Vercel Deployment Guide

This guide explains how to deploy "Web Gia Dụng Pro" to Vercel alongside the existing Render deployment.

## Overview

The application now supports dual-deployment:
- **Render.com**: Docker/Gunicorn with APScheduler for background jobs
- **Vercel**: Serverless Functions with cron jobs via API endpoints

## Prerequisites

1. **Vercel Account**: Sign up at [vercel.com](https://vercel.com)
2. **GitHub Repository**: The project must be on GitHub
3. **PostgreSQL Database**: External database (Supabase, Neon, or Render Postgres)
4. **Cloud Storage** (Optional): Cloudinary or Supabase Storage for image uploads

## Step 1: Configure Environment Variables

### In Vercel Dashboard

Go to your Vercel project → Settings → Environment Variables and add:

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `SECRET_KEY` | Flask secret key for sessions | `your_random_secret_key` |
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://user:pass@host:5432/db` |
| `VERCEL` | Platform detection | `true` |
| `CRON_SECRET_KEY` | Secret for cron job security | `your_random_cron_secret` |

### Optional Variables (Cloud Storage)

| Variable | Description | Example |
|----------|-------------|---------|
| `CLOUDINARY_CLOUD_NAME` | Cloudinary cloud name | `your_cloud_name` |
| `CLOUDINARY_API_KEY` | Cloudinary API key | `123456789` |
| `CLOUDINARY_API_SECRET` | Cloudinary API secret | `your_api_secret` |
| `SUPABASE_URL` | Supabase project URL | `https://xxx.supabase.co` |
| `SUPABASE_KEY` | Supabase anon key | `your_supabase_key` |
| `SUPABASE_BUCKET` | Supabase storage bucket | `uploads` |

### Optional Variables (AI & Payment)

| Variable | Description | Example |
|----------|-------------|---------|
| `GEMINI_API_KEY` | Google Gemini AI key | `your_gemini_key` |
| `VIETQR_BANK_CODE` | Bank code for QR payments | `MB` |
| `VIETQR_ACCOUNT_NO` | Account number for QR | `00931222` |
| `VIETQR_ACCOUNT_NAME` | Account name for QR | `HA MINH TRI` |
| `SEPAY_MERCHANT_ID` | SePay merchant ID | `SP-LIVE-THA8BB58` |
| `SEPAY_SECRET_KEY` | SePay secret key | `your_sepay_secret` |
| `PAYMENT_WEBHOOK_SECRET` | Webhook security | `your_webhook_secret` |

## Step 2: Set Up PostgreSQL Database

### Option A: Supabase (Recommended)

1. Create a free account at [supabase.com](https://supabase.com)
2. Create a new project
3. Go to Settings → Database
4. Copy the connection string (URI format)
5. Set `DATABASE_URL` in Vercel environment variables

### Option B: Neon

1. Create a free account at [neon.tech](https://neon.tech)
2. Create a new project
3. Copy the connection string
4. Set `DATABASE_URL` in Vercel environment variables

### Option C: Render Postgres

1. Create a PostgreSQL database on Render
2. Copy the internal database URL
3. Set `DATABASE_URL` in Vercel environment variables

### Initialize Database Schema

After setting up the database, you need to run the schema initialization. Since Vercel is serverless, you can:

1. **Temporarily deploy to Render** to run `init_db()`, then switch to Vercel
2. **Run locally** with the production database URL to initialize:
   ```bash
   export DATABASE_URL="your_production_database_url"
   python -c "from database.db import init_db; init_db()"
   ```

## Step 3: Configure Cloud Storage (Optional but Recommended)

Vercel has an ephemeral filesystem, so uploaded files will be lost after deployment. Configure cloud storage:

### Option A: Cloudinary

1. Create account at [cloudinary.com](https://cloudinary.com)
2. Get your Cloud Name, API Key, and API Secret from Dashboard
3. Set environment variables in Vercel

### Option B: Supabase Storage

1. In your Supabase project, go to Storage
2. Create a bucket named `uploads` (or your preferred name)
3. Make the bucket public
4. Set environment variables in Vercel

## Step 4: Deploy to Vercel

### Method A: Via Vercel Dashboard

1. Go to [vercel.com/new](https://vercel.com/new)
2. Import your GitHub repository
3. Vercel will auto-detect the Python configuration from `vercel.json`
4. Configure build settings (auto-detected):
   - **Build Command**: (auto-detected)
   - **Output Directory**: (auto-detected)
5. Add environment variables (see Step 1)
6. Click "Deploy"

### Method A: Via Vercel CLI

```bash
# Install Vercel CLI
npm install -g vercel

# Login to Vercel
vercel login

# Deploy from project root
vercel

# Follow prompts to configure
```

## Step 5: Configure Cron Jobs

The application uses Vercel Cron Jobs to cancel expired orders automatically.

### Cron Configuration

The cron job is already configured in `vercel.json`:

```json
"crons": [
  {
    "path": "/api/cron/cancel-expired-orders",
    "schedule": "*/15 * * * *"
  }
]
```

This runs every 15 minutes.

### Cron Security

The cron endpoint is protected by `CRON_SECRET_KEY`. Vercel automatically passes this as a header.

To test the cron endpoint manually:

```bash
curl -X POST https://your-app.vercel.app/api/cron/cancel-expired-orders \
  -H "X-Cron-Secret: your_cron_secret_key"
```

## Step 6: Verify Deployment

1. **Check the deployment**: Visit your Vercel URL
2. **Test database connection**: Try to browse products
3. **Test image upload**: Upload a banner or product image (if cloud storage configured)
4. **Test cron job**: Check logs in Vercel Dashboard

## Step 7: Configure Custom Domain (Optional)

1. In Vercel Dashboard → Settings → Domains
2. Add your custom domain
3. Update DNS records as instructed by Vercel

## Differences Between Render and Vercel

| Feature | Render | Vercel |
|---------|--------|--------|
| **Deployment Type** | Docker/Gunicorn | Serverless Functions |
| **Background Jobs** | APScheduler (in-process) | Cron Jobs (API endpoint) |
| **Filesystem** | Persistent | Ephemeral |
| **Image Storage** | Local `static/uploads/` | Cloudinary/Supabase required |
| **Database** | Render Postgres | External PostgreSQL required |
| **Cold Starts** | No | Yes (serverless) |
| **Scaling** | Vertical scaling | Auto-scaling |

## Troubleshooting

### Database Connection Issues

**Error**: `psycopg2.OperationalError: could not connect to server`

**Solution**:
- Verify `DATABASE_URL` is correct
- Check database allows connections from Vercel IPs
- Ensure SSL is enabled in connection string

### Image Upload Not Working

**Error**: Images not persisting after deployment

**Solution**:
- Configure Cloudinary or Supabase Storage
- Verify environment variables are set
- Check Vercel logs for upload errors

### Cron Job Not Running

**Error**: Cron job not executing

**Solution**:
- Verify `CRON_SECRET_KEY` is set
- Check Vercel Cron Jobs section in dashboard
- Test endpoint manually with curl

### Cold Start Delays

**Issue**: First request after inactivity is slow

**Solution**: This is normal for serverless. Consider:
- Using Vercel Edge Functions for static content
- Implementing caching strategies
- Keeping Render as primary deployment for critical paths

## Migration from Render to Vercel

If you want to migrate completely to Vercel:

1. **Export data from Render database**: Use `pg_dump`
2. **Import to new PostgreSQL**: Use `psql` or Supabase import
3. **Migrate images**: Upload local images to Cloudinary/Supabase
4. **Update DNS**: Point custom domain to Vercel
5. **Decommission Render**: After verifying Vercel deployment

## Dual Deployment Strategy

For maximum reliability, consider keeping both deployments active:

- **Render**: Primary production deployment (consistent performance)
- **Vercel**: Backup/edge deployment (global CDN)

Use DNS load balancing or feature flags to route traffic between platforms.

## Monitoring

### Vercel Dashboard

- **Analytics**: View traffic and performance
- **Logs**: Real-time function logs
- **Cron Jobs**: Monitor cron execution
- **Deployments**: Track deployment history

### Database Monitoring

Use your database provider's dashboard to monitor:
- Connection count
- Query performance
- Storage usage

## Security Best Practices

1. **Never commit `.env` file** to Git
2. **Use strong secrets** for `SECRET_KEY` and `CRON_SECRET_KEY`
3. **Enable SSL** for all database connections
4. **Restrict database access** to Vercel IPs only
5. **Rotate secrets** regularly
6. **Monitor logs** for suspicious activity

## Cost Considerations

### Vercel Free Tier

- 100GB bandwidth per month
- 6,000 minutes of execution time
- Unlimited deployments
- Cron jobs included

### Paid Features

- Custom domains (free on Pro plan)
- Edge functions
- Advanced analytics

### Database Costs

- Supabase: Free tier (500MB)
- Neon: Free tier (0.5GB)
- Render Postgres: $7/month minimum

### Cloud Storage

- Cloudinary: Free tier (25GB)
- Supabase Storage: Free tier (1GB)

## Support

- **Vercel Documentation**: [vercel.com/docs](https://vercel.com/docs)
- **Flask on Vercel**: [vercel.com/docs/concepts/functions/serverless-functions](https://vercel.com/docs/concepts/functions/serverless-functions)
- **Project Issues**: Check GitHub Issues
