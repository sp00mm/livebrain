# Oracle Cloud Free Tier Setup Guide

Complete guide to host LiveBrain on Oracle Cloud's Always Free Tier.

## What You Get (Free Forever)

- **Compute**: 2 AMD VMs (1/8 OCPU, 1GB RAM each) OR 1 Ampere ARM VM (4 cores, 24GB RAM)
- **Storage**: 200GB total block storage
- **Object Storage**: 20GB
- **Bandwidth**: 10TB outbound per month
- **Public IP**: 2 free

Perfect for hosting your website and model files!

## Part 1: Oracle Cloud Account Setup

### Step 1: Sign Up

1. Go to https://cloud.oracle.com/
2. Click "Sign up for free"
3. Choose your home region (IMPORTANT: Can't change later)
   - Recommend: US West (Phoenix) or US East (Ashburn)
4. Complete registration with:
   - Email address
   - Credit card (for verification only, won't be charged)
   - Phone verification

### Step 2: Verify Always Free Tier

After login, check top-right corner shows "Always Free"

## Part 2: Create Object Storage Bucket (For Models)

### Step 1: Create Bucket

1. In Oracle Console, click hamburger menu (☰)
2. Go to **Storage** → **Buckets**
3. Make sure you're in your home region (top-right)
4. Click **"Create Bucket"**
   - Name: `livebrain-models`
   - Storage Tier: `Standard`
   - Leave other defaults
5. Click **Create**

### Step 2: Upload Model Files

1. First, prepare models locally:
```bash
cd ~/Desktop/Projects/livebrain
./prepare_models.sh
```

2. In Oracle Console, click on your bucket `livebrain-models`
3. Click **"Upload"**
4. Select `embeddinggemma-onnx.zip` (~600MB)
5. Click **Upload**
6. Wait for upload to complete

### Step 3: Make Bucket Public

1. In bucket details, go to **"Object Lifecycle Policy"** tab
2. Actually, better way: Click on the uploaded object
3. Click the 3 dots menu → **"View Object Details"**
4. Under **"URL Path"**, note the URL structure

For public access:
1. Click bucket name → **"Edit Visibility"**
2. Select **"Public"**
3. Confirm

Or, create a Pre-Authenticated Request (PAR):
1. Click on object → 3 dots → **"Create Pre-Authenticated Request"**
2. Name: `models-public`
3. Access Type: **"Permit object reads"**
4. Expiration: Set far future date or leave empty
5. Click **Create**
6. **COPY THE URL** (you can't see it again!)

### Step 4: Get Object Storage URL

The URL will look like:
```
https://objectstorage.us-phoenix-1.oraclecloud.com/n/NAMESPACE/b/livebrain-models/o/embeddinggemma-onnx.zip
```

Or with PAR:
```
https://objectstorage.us-phoenix-1.oraclecloud.com/p/PAR_TOKEN/n/NAMESPACE/b/livebrain-models/o/embeddinggemma-onnx.zip
```

**Save this URL - you'll need it!**

## Part 3: Create VPS (Compute Instance)

### Step 1: Create Instance

1. Click hamburger menu → **Compute** → **Instances**
2. Click **"Create Instance"**

**Configure:**
- Name: `livebrain-web`
- Availability domain: Choose any
- Image: **Ubuntu 22.04** (under "Change Image")
- Shape: Click "Change Shape"
  - Choose **VM.Standard.A1.Flex** (ARM - 4 cores, 24GB RAM - FREE!)
  - Or **VM.Standard.E2.1.Micro** (AMD - 1/8 core, 1GB RAM - FREE!)
  - Recommend ARM for better performance
- Networking:
  - Create new virtual cloud network (default is fine)
  - Assign public IP: Yes
- Add SSH Keys:
  - Generate key pair (download both private and public keys)
  - Or paste your existing public key
- Boot volume: 50GB (default, within free tier)

3. Click **"Create"**
4. Wait ~2 minutes for provisioning
5. **Note the Public IP Address** (e.g., `123.45.67.89`)

### Step 2: Configure Firewall

1. On instance page, click **"Subnet"** link
2. Click your **"Default Security List"**
3. Click **"Add Ingress Rules"**

Add these rules:

**Rule 1 - HTTP:**
- Source CIDR: `0.0.0.0/0`
- IP Protocol: TCP
- Destination Port: `80`
- Description: HTTP

**Rule 2 - HTTPS:**
- Source CIDR: `0.0.0.0/0`
- IP Protocol: TCP
- Destination Port: `443`
- Description: HTTPS

4. Click **"Add Ingress Rules"**

## Part 4: Configure the VPS

### Step 1: Connect via SSH

```bash
# Make key private
chmod 600 ~/Downloads/ssh-key-*.key

# Connect (replace with your IP and key path)
ssh -i ~/Downloads/ssh-key-*.key ubuntu@YOUR_PUBLIC_IP
```

### Step 2: Update System

```bash
sudo apt update
sudo apt upgrade -y
```

### Step 3: Configure Ubuntu Firewall

```bash
# Open HTTP and HTTPS
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT

# Save rules
sudo netfilter-persistent save
```

### Step 4: Install Nginx

```bash
sudo apt install nginx -y
sudo systemctl start nginx
sudo systemctl enable nginx
```

Test: Open browser to `http://YOUR_PUBLIC_IP` - you should see Nginx welcome page!

### Step 5: Install Certbot (for HTTPS)

```bash
sudo apt install certbot python3-certbot-nginx -y
```

## Part 5: Setup Website

### Step 1: Create Website Directory

```bash
sudo mkdir -p /var/www/livebrain
sudo chown -R $USER:$USER /var/www/livebrain
chmod -R 755 /var/www/livebrain
```

### Step 2: Create Website Files

```bash
cd /var/www/livebrain

# Create simple download page
cat > index.html << 'EOF'
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LiveBrain - Document Search</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        .container {
            background: white;
            border-radius: 20px;
            padding: 60px;
            max-width: 600px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            text-align: center;
        }
        h1 {
            font-size: 3em;
            margin-bottom: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        p {
            color: #666;
            font-size: 1.2em;
            margin-bottom: 40px;
            line-height: 1.6;
        }
        .download-btn {
            display: inline-block;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 18px 50px;
            border-radius: 50px;
            text-decoration: none;
            font-size: 1.2em;
            font-weight: 600;
            transition: transform 0.2s, box-shadow 0.2s;
            box-shadow: 0 10px 30px rgba(102, 126, 234, 0.4);
        }
        .download-btn:hover {
            transform: translateY(-3px);
            box-shadow: 0 15px 40px rgba(102, 126, 234, 0.6);
        }
        .version {
            margin-top: 30px;
            color: #999;
            font-size: 0.9em;
        }
        .features {
            margin-top: 40px;
            text-align: left;
            color: #666;
        }
        .features li {
            margin: 10px 0;
            padding-left: 25px;
            position: relative;
        }
        .features li:before {
            content: "✓";
            position: absolute;
            left: 0;
            color: #667eea;
            font-weight: bold;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>LiveBrain</h1>
        <p>Local AI-powered document search for your files</p>
        <a href="LiveBrain-1.0.0.dmg" class="download-btn" download>
            Download for Mac
        </a>
        <p class="version">Version 1.0.0 • ~50MB • macOS 14.0+</p>
        
        <ul class="features">
            <li>Search documents semantically</li>
            <li>100% local processing</li>
            <li>Fast vector similarity search</li>
            <li>Supports PDFs, text files & more</li>
        </ul>
    </div>
</body>
</html>
EOF

# Create updates directory
mkdir updates

# Create version.json
cat > version.json << 'EOF'
{
  "version": "1.0.0",
  "url": "https://yourdomain.com/livebrain/LiveBrain-1.0.0.dmg",
  "notes": "Initial release"
}
EOF
```

### Step 3: Configure Nginx

```bash
sudo nano /etc/nginx/sites-available/livebrain
```

Paste this configuration (replace `yourdomain.com`):

```nginx
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;
    
    root /var/www/livebrain;
    index index.html;
    
    location / {
        try_files $uri $uri/ =404;
    }
    
    # Enable large file uploads
    client_max_body_size 1G;
    
    # Cache static files
    location ~* \.(dmg|zip)$ {
        add_header Cache-Control "public, max-age=31536000";
    }
}
```

Enable the site:
```bash
sudo ln -s /etc/nginx/sites-available/livebrain /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

## Part 6: Domain Setup (Optional)

### Option A: Use Your Domain

1. Go to your domain registrar (Namecheap, GoDaddy, etc.)
2. Add an A record:
   - Type: `A`
   - Name: `@` (or subdomain like `livebrain`)
   - Value: `YOUR_PUBLIC_IP`
   - TTL: `300`

3. Wait 5-10 minutes for DNS propagation

4. Setup HTTPS:
```bash
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
```

### Option B: Use Oracle IP Directly

Just use `http://YOUR_PUBLIC_IP/` (no HTTPS)

## Part 7: Upload Your DMG

From your Mac:

```bash
cd ~/Desktop/Projects/livebrain

# Upload DMG to server
scp -i ~/Downloads/ssh-key-*.key \
    LiveBrain-1.0.0.dmg \
    ubuntu@YOUR_PUBLIC_IP:/var/www/livebrain/
```

## Part 8: Update Your App

Update `updater.py` with your URLs:

```python
UPDATE_URL = "http://YOUR_PUBLIC_IP/version.json"
MODEL_URL = "https://objectstorage.REGION.oraclecloud.com/n/NAMESPACE/b/livebrain-models/o/embeddinggemma-onnx.zip"
```

Or with domain:
```python
UPDATE_URL = "https://yourdomain.com/livebrain/version.json"
MODEL_URL = "https://objectstorage.us-phoenix-1.oraclecloud.com/..."
```

## Part 9: Test Everything

1. Visit your site: `http://YOUR_PUBLIC_IP` or `https://yourdomain.com`
2. Download button should work
3. Test version.json: `curl http://YOUR_PUBLIC_IP/version.json`
4. Test model download: `curl -I "YOUR_ORACLE_STORAGE_URL"`

## Pushing Updates

```bash
# Build new version
cd ~/Desktop/Projects/livebrain
./build.sh

# Upload to server
scp -i ~/Downloads/ssh-key-*.key \
    LiveBrain-1.0.1.dmg \
    ubuntu@YOUR_PUBLIC_IP:/var/www/livebrain/updates/

# SSH into server and update version.json
ssh -i ~/Downloads/ssh-key-*.key ubuntu@YOUR_PUBLIC_IP

# Edit version.json
nano /var/www/livebrain/version.json
```

Update to:
```json
{
  "version": "1.0.1",
  "url": "https://yourdomain.com/livebrain/updates/LiveBrain-1.0.1.dmg",
  "notes": "Bug fixes and improvements"
}
```

## Monitoring & Maintenance

### Check Nginx Logs
```bash
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

### Check Disk Space
```bash
df -h
```

### Download Statistics
```bash
grep "LiveBrain.*\.dmg" /var/log/nginx/access.log | wc -l
```

## Cost Breakdown

- **VPS**: $0/month (Always Free)
- **Object Storage**: $0/month (first 20GB free)
- **Bandwidth**: $0/month (first 10TB free)
- **Domain** (optional): $10-15/year

**Total: FREE** (or just domain cost)

## Troubleshooting

### Can't connect to VPS
- Check security list has port 80/443 open
- Check Ubuntu firewall: `sudo iptables -L`

### Website not loading
- Check Nginx: `sudo systemctl status nginx`
- Check logs: `sudo tail /var/log/nginx/error.log`

### Model download fails
- Check Object Storage bucket is public
- Test URL in browser
- Check PAR hasn't expired

### Out of space
- Oracle Free Tier includes 200GB total
- Check usage: `df -h`
- Clean old versions: `rm /var/www/livebrain/updates/*.dmg`

## Security Best Practices

1. **Keep system updated:**
```bash
sudo apt update && sudo apt upgrade -y
```

2. **Setup UFW firewall:**
```bash
sudo ufw allow 22
sudo ufw allow 80
sudo ufw allow 443
sudo ufw enable
```

3. **Disable password auth:**
```bash
sudo nano /etc/ssh/sshd_config
# Set: PasswordAuthentication no
sudo systemctl restart sshd
```

4. **Regular backups:**
```bash
# Backup website
tar -czf livebrain-backup-$(date +%Y%m%d).tar.gz /var/www/livebrain
```

## Next Steps

- [ ] Set up monitoring (e.g., UptimeRobot)
- [ ] Add analytics (e.g., Plausible, self-hosted)
- [ ] Setup automated backups
- [ ] Add release notes page
- [ ] Create API for update checks (more secure)

---

You now have a completely free, production-ready hosting setup for LiveBrain! 🎉

