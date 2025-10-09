#!/bin/bash

echo "Preparing models for cloud storage (q4 only)..."

cd models/embeddinggemma-onnx

# Create a lightweight zip with only q4 model and necessary files
zip -r ../../embeddinggemma-onnx.zip \
    config.json \
    tokenizer.json \
    tokenizer_config.json \
    special_tokens_map.json \
    added_tokens.json \
    generation_config.json \
    onnx/model_q4.onnx \
    onnx/model_q4.onnx_data

cd ../..

echo "Created embeddinggemma-onnx.zip"
echo "Size: $(du -h embeddinggemma-onnx.zip | cut -f1)"
echo ""
echo "=== AWS S3 Upload ==="
echo "  aws s3 cp embeddinggemma-onnx.zip s3://yourbucket/ --acl public-read"
echo "  URL: https://yourbucket.s3.amazonaws.com/embeddinggemma-onnx.zip"
echo ""
echo "=== Oracle Cloud Upload ==="
echo "  1. Go to Oracle Console → Storage → Buckets"
echo "  2. Upload embeddinggemma-onnx.zip to your bucket"
echo "  3. Make bucket public or create Pre-Authenticated Request"
echo "  4. Copy the object URL"
echo ""
echo "Update updater.py MODEL_URL with your cloud storage URL"

