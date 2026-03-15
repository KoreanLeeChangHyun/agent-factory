---
name: devops-ci-pipeline
description: "Designs and configures CI/CD pipelines covering build/test/deploy stage composition, caching strategies, secret management, and monorepo pipeline patterns. Use when setting up or optimizing a CI/CD pipeline, designing build and deploy stages, configuring pipeline caching, managing secrets and environment variables in continuous integration, or automating deployment for monorepo projects."
license: "Apache-2.0"
---

# CI/CD 파이프라인 스킬

빌드/테스트/배포 파이프라인 설계 및 최적화 가이드. GitHub Actions를 중심으로 하되 범용 원칙을 포함합니다.

## 파이프라인 설계 원칙

1. **Fast Feedback**: 빠른 실패 → 빠른 피드백 (lint → unit test → integration test 순)
2. **캐싱 우선**: 반복 빌드 비용 최소화 (deps, build artifacts, docker layers)
3. **시크릿 격리**: 환경별 시크릿 분리, 로그에 노출 금지
4. **멱등성**: 동일 입력 → 동일 결과 (재현 가능한 빌드)
5. **최소 권한**: 배포 토큰은 필요한 리소스에만 접근

## GitHub Actions 표준 구조

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true          # 중복 실행 자동 취소

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: npm                 # 빌트인 캐싱
      - run: npm ci
      - run: npm run lint
      - run: npm run type-check

  test:
    needs: lint
    runs-on: ubuntu-latest
    strategy:
      matrix:
        node-version: [18, 20]      # 매트릭스 빌드
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: ${{ matrix.node-version }}
          cache: npm
      - run: npm ci
      - run: npm test -- --coverage
      - uses: actions/upload-artifact@v4
        with:
          name: coverage-${{ matrix.node-version }}
          path: coverage/

  build:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-buildx-action@v3
      - uses: docker/build-push-action@v5
        with:
          context: .
          push: false
          cache-from: type=gha     # GitHub Actions 캐시 활용
          cache-to: type=gha,mode=max

  deploy:
    needs: build
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    environment: production         # 환경 보호 규칙 적용
    steps:
      - uses: actions/checkout@v4
      - run: echo "Deploy to production"
        env:
          DEPLOY_TOKEN: ${{ secrets.DEPLOY_TOKEN }}
```

## 캐싱 전략

### 의존성 캐싱

```yaml
# Node.js
- uses: actions/setup-node@v4
  with:
    cache: npm        # package-lock.json 해시로 자동 캐싱

# Python
- uses: actions/setup-python@v5
  with:
    python-version: 3.12
    cache: pip        # requirements*.txt 해시로 자동 캐싱

# 커스텀 캐싱 (pnpm, poetry 등)
- uses: actions/cache@v4
  with:
    path: ~/.pnpm-store
    key: pnpm-${{ hashFiles('pnpm-lock.yaml') }}
    restore-keys: pnpm-
```

### Docker 레이어 캐싱

```yaml
- uses: docker/build-push-action@v5
  with:
    cache-from: type=gha
    cache-to: type=gha,mode=max
```

## 시크릿 관리

### 환경별 시크릿 분리

```yaml
# GitHub Environments 활용
environment: production   # Settings > Environments > production에 시크릿 등록

# 환경 보호 규칙
# - Required reviewers: 프로덕션 배포 승인자 지정
# - Wait timer: 배포 전 대기 시간 (분)
```

### 시크릿 사용 패턴

```yaml
steps:
  - name: Deploy
    env:
      API_KEY: ${{ secrets.API_KEY }}     # 환경변수로 주입
    run: ./deploy.sh
    # secrets는 run 블록에서 직접 참조 금지: ${{ secrets.X }} in run
    # 로그에 마스킹되지만 명시적 주입 권장
```

## 모노레포 파이프라인

### 변경 감지 기반 선택적 실행

```yaml
jobs:
  changes:
    runs-on: ubuntu-latest
    outputs:
      frontend: ${{ steps.filter.outputs.frontend }}
      backend: ${{ steps.filter.outputs.backend }}
    steps:
      - uses: dorny/paths-filter@v3
        id: filter
        with:
          filters: |
            frontend:
              - 'packages/frontend/**'
            backend:
              - 'packages/backend/**'

  test-frontend:
    needs: changes
    if: needs.changes.outputs.frontend == 'true'
    runs-on: ubuntu-latest
    steps:
      - run: cd packages/frontend && npm test

  test-backend:
    needs: changes
    if: needs.changes.outputs.backend == 'true'
    runs-on: ubuntu-latest
    steps:
      - run: cd packages/backend && npm test
```

## 단계별 배포 패턴

| 패턴 | 구성 | 적합 시나리오 |
|------|------|-------------|
| Blue-Green | 두 환경 교대 전환 | 무중단 배포, 즉시 롤백 필요 |
| Canary | 일부 트래픽 점진 전환 | 대규모 서비스, 리스크 최소화 |
| Rolling | 인스턴스 순차 교체 | 쿠버네티스 기본, 점진적 전환 |
| Feature Flag | 코드 배포 후 기능 ON/OFF | 기능 단위 제어, A/B 테스트 |

## 품질 게이트

```yaml
# PR 머지 필수 조건 (branch protection rules)
required_status_checks:
  - lint
  - test (18)
  - test (20)
  - build
required_pull_request_reviews:
  required_approving_review_count: 1
```
