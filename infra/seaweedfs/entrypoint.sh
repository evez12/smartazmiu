#!/bin/sh
# Renders the S3 identity file from environment variables so credentials never live in the repo.
set -eu
cat > /tmp/s3.json <<JSON
{
  "identities": [
    {
      "name": "smartazmiu-api",
      "credentials": [{ "accessKey": "${S3_ACCESS_KEY}", "secretKey": "${S3_SECRET_KEY}" }],
      "actions": ["Admin", "Read", "Write", "List", "Tagging"]
    }
  ]
}
JSON
exec weed server -dir=/data -ip.bind=0.0.0.0 -master.volumeSizeLimitMB=256 -s3 -s3.config=/tmp/s3.json
