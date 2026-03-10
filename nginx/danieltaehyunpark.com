server {
    listen 80;
    listen [::]:80;
    server_name danieltaehyunpark.com www.danieltaehyunpark.com;

    # Redirect all HTTP to HTTPS
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    listen [::]:443 ssl;
    server_name danieltaehyunpark.com www.danieltaehyunpark.com;

    root /var/www/danieltaehyunpark.com;
    index index.html;

    # SSL — managed by Certbot
    ssl_certificate     /etc/letsencrypt/live/danieltaehyunpark.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/danieltaehyunpark.com/privkey.pem;
    include             /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam         /etc/letsencrypt/ssl-dhparams.pem;

    # Security headers
    add_header X-Frame-Options        "SAMEORIGIN"   always;
    add_header X-Content-Type-Options "nosniff"      always;
    add_header Referrer-Policy        "strict-origin-when-cross-origin" always;
    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload" always;

    # Gzip
    gzip on;
    gzip_types text/html text/css text/javascript application/javascript;

    location / {
        try_files $uri $uri/ =404;
    }

    # Cache static assets
    location ~* \.(css|js|ico|png|jpg|jpeg|svg|woff2?)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    access_log /var/log/nginx/danieltaehyunpark.com.access.log;
    error_log  /var/log/nginx/danieltaehyunpark.com.error.log;
}
