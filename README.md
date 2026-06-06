# Lambda Chunking Demo

Text intră. Bucăți ies. Simplu.

```
S3 input/ --> Lambda --> S3 output/
                |
                +--> DLQ (dacă crăpă)
```

## Ce face

- Pui fișier text în S3 folder `input/`
- Lambda taie textul în bucăți mici (500 chars, 50 overlap)
- JSON apare în `output/`
- Dacă crăpă, mesaj merge în DLQ. Nimic nu se pierde.

## Fișiere

```
src/app.py          # creierul lambda
template.yaml       # tot AWS-ul
tests/              # 8 teste
sample_files/       # 10 fișiere demo
```

## 4 butoane în GitHub Actions

| Buton | Ce face |
|-------|---------|
| CI | Testează cod. Nu atinge AWS. |
| Deploy | Face/updatează AWS |
| Manual Invoke | Cheamă lambda direct |
| Destroy | Șterge tot. Scrie DELETE întâi. |

---

## Setup (o singură dată)

### 1. Chestii AWS

Fă IAM user `github-actions-chunking-demo` cu policies:
- `AWSCloudFormationFullAccess`
- `AWSLambda_FullAccess`
- `AmazonS3FullAccess`
- `IAMFullAccess`
- `AmazonSQSFullAccess`
- `CloudWatchFullAccess`

Ia access key. Salvează ambele părți. Secret-ul îl vezi o singură dată.

### 2. GitHub secrets

Du-te: Repo → Settings → Secrets and variables → Actions

Adaugă secrets:
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`

Adaugă variable:
- `BUCKET_NAME` — alege nume unic, lowercase, fără underscore

### 3. Deploy

Actions → Deploy and Demo → Run workflow → gata.

---

## Cum folosești

### Urcă fișier (cel mai des)

```bash
aws s3 cp fisier.txt s3://bucket-name/input/
```

Așteaptă câteva secunde. Verifică `output/` pentru JSON.

Sau trage fișier în S3 console. Același lucru.

### Updatează cod

Schimbă `src/app.py`. Push. Rulează Deploy workflow.

### Șterge tot

Actions → Destroy Stack → scrie `DELETE` → run.

---

## Test local

```bash
pip install pytest boto3 ruff
pytest tests/ -v
sam build
sam local invoke ChunkingFunction --event events/s3-put.json
```

---

## Cum taie textul

1. Ia 500 chars
2. Caută loc bun de tăiat (. ! ? sau newline sau spațiu)
3. Următoarea bucată începe cu 50 chars înainte de sfârșitul ultimei
4. Repetă până gata

Schimbi în `template.yaml`: `ChunkSize`, `ChunkOverlap`

---

## Cost

Gratis. Poate $0.10/lună pentru alarm. Fișierele se șterg singure după 7 zile.

---

## Probleme?

| Eroare | Rezolvare |
|--------|-----------|
| BucketAlreadyExists | Alege alt nume bucket |
| AccessDenied | Verifică IAM policies |
| Lambda nu merge | Vezi CloudWatch logs |
| Stack stricat | Rulează Destroy, apoi Deploy iar |
