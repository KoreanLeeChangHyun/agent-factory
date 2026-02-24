# Insecure Defaults Reference

안전하지 않은 기본값과 하드코딩 시크릿 탐지를 위한 언어별 체크리스트.

## Table of Contents

- [하드코딩 시크릿 탐지 패턴](#하드코딩-시크릿-탐지-패턴)
- [안전하지 않은 기본값 목록](#안전하지-않은-기본값-목록)
- [Python 보안 기본값 체크리스트](#python-보안-기본값-체크리스트)
- [JavaScript/TypeScript 보안 기본값 체크리스트](#javascripttypescript-보안-기본값-체크리스트)
- [Go 보안 기본값 체크리스트](#go-보안-기본값-체크리스트)
- [Rust 보안 기본값 체크리스트](#rust-보안-기본값-체크리스트)

## 하드코딩 시크릿 탐지 패턴

### 변수명 기반 탐지

다음 변수명에 리터럴 문자열이 할당된 경우 경고:

```
password, passwd, pwd, secret, token, api_key, apikey, api_secret,
access_key, access_token, auth_token, credentials, private_key,
encryption_key, signing_key, client_secret, db_password, database_url
```

### 정규식 패턴

```regex
# 일반 시크릿 할당
(?i)(password|secret|token|api.?key|credential)\s*[=:]\s*['"][^'"]{8,}['"]

# AWS Access Key
AKIA[0-9A-Z]{16}

# AWS Secret Key
(?i)aws.?secret.?access.?key\s*[=:]\s*['"][A-Za-z0-9/+=]{40}['"]

# GitHub Token
gh[pousr]_[A-Za-z0-9_]{36,}

# Slack Token
xox[baprs]-[0-9a-zA-Z-]+

# Google API Key
AIza[0-9A-Za-z_-]{35}

# Stripe Key
sk_live_[0-9a-zA-Z]{24,}

# JWT (하드코딩)
eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]+

# Private Key 헤더
-----BEGIN (RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----

# Connection String (패스워드 포함)
(?i)(mongodb|postgres|mysql|redis)://[^:]+:[^@]+@
```

### 허용 예외

다음은 시크릿으로 오탐하지 않는다:

- 환경변수 참조: `process.env.API_KEY`, `os.environ["SECRET"]`, `env::var("TOKEN")`
- 설정 파일 참조: `config.get("password")`, `settings.SECRET_KEY`
- 테스트 전용 값: `test_`, `mock_`, `fake_`, `dummy_` 접두사
- 플레이스홀더: `<your-key-here>`, `TODO`, `CHANGE_ME`, `xxx`

## 안전하지 않은 기본값 목록

### 공통 위험 기본값

| 기본값 | 위험 | 안전한 대안 |
|--------|------|------------|
| `DEBUG=True` | 에러 상세 노출, 성능 저하 | 환경변수로 분리, 프로덕션에서 False |
| `CORS: *` | 모든 도메인에서 접근 허용 | 허용 도메인 화이트리스트 |
| `SSL verify=False` | MITM 공격 가능 | 항상 True, 인증서 고정 |
| `admin/admin` | 기본 자격증명 | 초기 설정 시 강제 변경 |
| `0.0.0.0:8080` | 모든 인터페이스 바인딩 | 필요한 인터페이스만 바인딩 |
| `chmod 777` | 모든 사용자 읽기/쓰기/실행 | 최소 권한 (644, 755) |
| `jwt.decode(verify=False)` | 서명 미검증 | verify=True (기본) |
| `cookie: httpOnly=false` | XSS로 쿠키 탈취 가능 | httpOnly=true |
| `SameSite=None` | CSRF 취약 | SameSite=Lax 또는 Strict |
| `X-Powered-By` 헤더 노출 | 기술 스택 노출 | 헤더 제거 |

### 데이터베이스 위험 기본값

| 기본값 | 위험 | 안전한 대안 |
|--------|------|------------|
| `trust` 인증 (PostgreSQL) | 패스워드 없이 접속 | `md5` 또는 `scram-sha-256` |
| `bind-address 0.0.0.0` (MySQL) | 외부 접속 허용 | `127.0.0.1` 또는 소켓 |
| `requirepass` 미설정 (Redis) | 인증 없이 접속 | 강력한 패스워드 설정 |
| root 계정 직접 사용 | 과도한 권한 | 애플리케이션 전용 계정 생성 |

## Python 보안 기본값 체크리스트

### 위험 패턴 -> 안전한 대안

| 위험 코드 | 문제 | 안전한 코드 |
|-----------|------|------------|
| `pickle.loads(data)` | 임의 코드 실행 | `json.loads(data)` 또는 입력 검증 |
| `eval(user_input)` | 코드 인젝션 | `ast.literal_eval()` 또는 파싱 |
| `subprocess.call(cmd, shell=True)` | 커맨드 인젝션 | `subprocess.call(cmd_list, shell=False)` |
| `yaml.load(data)` | 코드 실행 | `yaml.safe_load(data)` |
| `hashlib.md5(password)` | 약한 해시 | `bcrypt.hashpw()` 또는 `argon2` |
| `random.random()` (보안 용도) | 예측 가능한 난수 | `secrets.token_hex()` |
| `tempfile.mktemp()` | 레이스 컨디션 | `tempfile.mkstemp()` |
| `requests.get(url, verify=False)` | SSL 미검증 | `requests.get(url, verify=True)` |
| `flask.send_file(user_path)` | 경로 탈출 | `flask.send_from_directory(safe_dir, filename)` |
| `os.system(cmd)` | 커맨드 인젝션 | `subprocess.run(cmd_list, check=True)` |

### Django 특화

| 설정 | 위험 기본값 | 안전한 값 |
|------|-----------|----------|
| `SECRET_KEY` | 하드코딩 | 환경변수에서 로드 |
| `DEBUG` | True | 프로덕션에서 False |
| `ALLOWED_HOSTS` | `['*']` | 명시적 호스트 목록 |
| `CSRF_COOKIE_SECURE` | False | True (HTTPS 환경) |
| `SESSION_COOKIE_SECURE` | False | True (HTTPS 환경) |
| `SECURE_BROWSER_XSS_FILTER` | False | True |

### Flask 특화

| 설정 | 위험 기본값 | 안전한 값 |
|------|-----------|----------|
| `SECRET_KEY` | 하드코딩/짧은 값 | 최소 32바이트 랜덤 |
| `SESSION_COOKIE_HTTPONLY` | True (OK) | True 유지 확인 |
| `SESSION_COOKIE_SAMESITE` | None | 'Lax' |
| `MAX_CONTENT_LENGTH` | 무제한 | 적절한 크기 제한 |

## JavaScript/TypeScript 보안 기본값 체크리스트

### 위험 패턴 -> 안전한 대안

| 위험 코드 | 문제 | 안전한 코드 |
|-----------|------|------------|
| `eval(userInput)` | 코드 인젝션 | JSON.parse() 또는 파서 사용 |
| `innerHTML = userInput` | XSS | textContent 또는 DOMPurify |
| `document.write(data)` | XSS | DOM API 사용 |
| `new Function(userCode)` | 코드 실행 | 샌드박스 환경 사용 |
| `JSON.parse(untrusted)` (무검증) | 프로토타입 오염 | 스키마 검증 (zod, joi) |
| `RegExp(userInput)` | ReDoS | 입력 이스케이프 또는 제한 |
| `crypto.randomBytes` 미사용 | 약한 난수 | `crypto.randomBytes()` |
| `child_process.exec(cmd)` | 커맨드 인젝션 | `execFile()` 또는 인자 배열 |

### Express 특화

| 설정 | 위험 기본값 | 안전한 값 |
|------|-----------|----------|
| `trust proxy` | false | 프록시 뒤에서 true + 범위 지정 |
| `x-powered-by` | 활성화 | `app.disable('x-powered-by')` |
| helmet 미사용 | 보안 헤더 없음 | `app.use(helmet())` |
| 쿠키 secret | 미설정/약함 | 강력한 랜덤 값 |
| CORS | 미설정 또는 `*` | origin 화이트리스트 |

### Next.js 특화

| 설정 | 위험 기본값 | 안전한 값 |
|------|-----------|----------|
| `images.domains` | 미제한 | 허용 도메인 명시 |
| API 라우트 인증 | 없음 | 미들웨어에서 인증 검사 |
| 환경변수 노출 | `NEXT_PUBLIC_` 접두사 | 서버 전용 변수는 접두사 없이 |
| `headers()` CSP | 미설정 | next.config.js에 CSP 설정 |

## Go 보안 기본값 체크리스트

### 위험 패턴 -> 안전한 대안

| 위험 코드 | 문제 | 안전한 코드 |
|-----------|------|------------|
| `http.ListenAndServe` (TLS 없음) | 평문 전송 | `http.ListenAndServeTLS` |
| `sql.Query(fmt.Sprintf(...))` | SQL 인젝션 | `sql.Query("SELECT ... WHERE id = $1", id)` |
| `template.HTML(userInput)` | XSS | `template.HTMLEscapeString()` |
| `os/exec.Command(userInput)` | 커맨드 인젝션 | 인자 배열로 분리 |
| `crypto/rand` 미사용 | 약한 난수 | `crypto/rand.Read()` |
| `tls.Config{InsecureSkipVerify: true}` | TLS 미검증 | `InsecureSkipVerify: false` |
| 에러 무시 `_, _ = fn()` | 에러 처리 누락 | 모든 에러 처리 |
| `ioutil.ReadAll` (크기 미제한) | 메모리 DoS | `io.LimitReader` 사용 |

### net/http 서버 설정

| 설정 | 위험 기본값 | 안전한 값 |
|------|-----------|----------|
| ReadTimeout | 0 (무제한) | 5-30초 |
| WriteTimeout | 0 (무제한) | 10-60초 |
| MaxHeaderBytes | 1MB | 필요한 최소값 |
| IdleTimeout | 0 (무제한) | 60-120초 |

## Rust 보안 기본값 체크리스트

### 위험 패턴 -> 안전한 대안

| 위험 코드 | 문제 | 안전한 코드 |
|-----------|------|------------|
| `unsafe { }` 블록 | 메모리 안전성 위반 가능 | 최소화, 반드시 주석으로 안전성 증명 |
| `.unwrap()` 무분별 사용 | 패닉 발생 | `?` 연산자 또는 `match`/`if let` |
| `std::mem::transmute` | 타입 안전성 우회 | 안전한 변환 API 사용 |
| `String::from_utf8_unchecked` | 잘못된 UTF-8 | `String::from_utf8()` 검증 |
| 외부 입력 `format!` | 포맷 문자열 인젝션 | 리터럴 포맷 문자열만 사용 |

### Cargo.toml 보안 설정

| 설정 | 권장 |
|------|------|
| `[profile.release] overflow-checks` | true |
| `edition` | 최신 (2024) |
| 의존성 버전 | 정확한 버전 또는 `~` 사용 |
| `cargo-audit` | CI에서 정기 실행 |

### Actix-web/Axum 특화

| 설정 | 위험 기본값 | 안전한 값 |
|------|-----------|----------|
| CORS | 미설정 | 명시적 origin 화이트리스트 |
| Rate Limiting | 없음 | actix-governor 또는 tower 미들웨어 |
| 요청 크기 제한 | 프레임워크 기본값 | 애플리케이션에 적합한 크기 |
| TLS | 미설정 | rustls 또는 native-tls |
