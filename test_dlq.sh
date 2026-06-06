#!/bin/bash

# Test DLQ - Generează și uploadează un fișier prea mare pentru Lambda (286MB > 256MB RAM)

BUCKET="lambda-chunking-demo"
REGION="eu-central-1"
FILE="huge_file.txt"

echo "=== Test DLQ: OutOfMemory ==="
echo ""

# 1. Generează fișier de ~286MB
echo "1. Generez fișier de 286MB..."
yes "Lorem ipsum dolor sit amet consectetur adipiscing elit. " | head -c 300000000 > $FILE
ls -lh $FILE

# 2. Upload în S3
echo ""
echo "2. Upload în S3..."
aws s3 cp $FILE s3://$BUCKET/input/$FILE --region $REGION

# 3. Cleanup local
rm $FILE
echo ""
echo "3. Fișier local șters."

echo ""
echo "=== Done! ==="
echo ""
echo "Lambda va încerca să proceseze → OutOfMemory → 2 retry-uri → DLQ"
echo ""
echo "Verifică în ~2-3 minute:"
echo "  - CloudWatch Logs pentru erori"
echo "  - SQS DLQ pentru mesajul eșuat:"
echo ""
echo "    aws sqs receive-message --queue-url \$(aws sqs get-queue-url --queue-name chunking-dlq --region $REGION --query QueueUrl --output text) --region $REGION"
