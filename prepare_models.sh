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

echo ""
echo "✅ Created embeddinggemma-onnx.zip"
echo "Size: $(du -h embeddinggemma-onnx.zip | cut -f1)"
echo ""
echo "Next steps:"
echo "  cd ../scripts && ./upload-models.sh"
echo ""
echo "This will upload to Oracle Object Storage at:"
echo "  https://objectstorage.us-chicago-1.oraclecloud.com/n/axa3tfnfy6dd/b/livebrain-models/o/embeddinggemma-onnx.zip"

