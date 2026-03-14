---
name: document-office/docx
description: "Comprehensive document creation, editing, and analysis with support for tracked changes, comments, formatting preservation, and text extraction. When Claude needs to work with professional documents (.docx files) for: (1) Creating new documents, (2) Modifying or editing content, (3) Working with tracked changes, (4) Adding comments, or any other document tasks"
license: Proprietary. LICENSE.txt has complete terms
---

# DOCX 생성, 편집, 분석

## 개요

사용자가 .docx 파일의 생성, 편집, 또는 내용 분석을 요청할 수 있다. .docx 파일은 본질적으로 읽거나 편집할 수 있는 XML 파일과 기타 리소스를 포함하는 ZIP 아카이브다. 작업 유형에 따라 다양한 도구와 워크플로우를 사용할 수 있다.

## 워크플로우 결정 트리

### 내용 읽기/분석
아래의 "텍스트 추출" 또는 "Raw XML 접근" 섹션을 사용한다

### 새 문서 생성
"새 Word 문서 생성" 워크플로우를 사용한다

### 기존 문서 편집
- **직접 작성한 문서 + 단순 변경**
  "기본 OOXML 편집" 워크플로우를 사용한다

- **타인이 작성한 문서**
  **"레드라인 워크플로우"** 사용을 권장한다 (기본 권장)

- **법률, 학술, 비즈니스, 정부 문서**
  **"레드라인 워크플로우"** 사용이 필수다

## 내용 읽기 및 분석

### 텍스트 추출
문서의 텍스트 내용만 읽으면 되는 경우, pandoc을 사용해 문서를 마크다운으로 변환한다. Pandoc은 문서 구조 보존 및 변경 추적 표시를 훌륭하게 지원한다:

```bash
# 변경 추적과 함께 문서를 마크다운으로 변환
pandoc --track-changes=all path-to-file.docx -o output.md
# 옵션: --track-changes=accept/reject/all
```

### Raw XML 접근
다음 항목에는 Raw XML 접근이 필요하다: 주석, 복잡한 서식, 문서 구조, 삽입된 미디어, 메타데이터. 이러한 기능을 사용하려면 문서를 압축 해제하고 Raw XML 내용을 읽어야 한다.

#### 파일 압축 해제
`python ooxml/scripts/unpack.py <office_file> <output_directory>`

#### 핵심 파일 구조
* `word/document.xml` - 문서 본문
* `word/comments.xml` - document.xml에서 참조되는 주석
* `word/media/` - 삽입된 이미지 및 미디어 파일
* 변경 추적은 `<w:ins>` (삽입) 및 `<w:del>` (삭제) 태그를 사용한다

## 새 Word 문서 생성

처음부터 새 Word 문서를 생성할 때는 **docx-js**를 사용한다. JavaScript/TypeScript로 Word 문서를 생성할 수 있다.

### 워크플로우
1. **필수 - 전체 파일 읽기**: [`docx-js.md`](docx-js.md)(약 500줄)를 처음부터 끝까지 완전히 읽는다. **이 파일을 읽을 때 절대 범위 제한을 설정하지 않는다.** 문서 생성을 진행하기 전에 상세 구문, 중요한 서식 규칙, 모범 사례를 위해 전체 파일 내용을 읽는다.
2. Document, Paragraph, TextRun 컴포넌트를 사용해 JavaScript/TypeScript 파일을 생성한다 (모든 의존성이 설치되어 있다고 가정하지만, 그렇지 않은 경우 아래 의존성 섹션을 참조한다)
3. Packer.toBuffer()를 사용해 .docx로 내보낸다

## 기존 Word 문서 편집

기존 Word 문서를 편집할 때는 **Document 라이브러리**(OOXML 조작을 위한 Python 라이브러리)를 사용한다. 이 라이브러리는 인프라 설정을 자동으로 처리하고 문서 조작 메서드를 제공한다. 복잡한 시나리오에서는 라이브러리를 통해 기본 DOM에 직접 접근할 수 있다.

### 워크플로우
1. **필수 - 전체 파일 읽기**: [`ooxml.md`](ooxml.md)(약 600줄)를 처음부터 끝까지 완전히 읽는다. **이 파일을 읽을 때 절대 범위 제한을 설정하지 않는다.** Document 라이브러리 API와 문서 파일 직접 편집을 위한 XML 패턴을 위해 전체 파일 내용을 읽는다.
2. 문서 압축 해제: `python ooxml/scripts/unpack.py <office_file> <output_directory>`
3. Document 라이브러리를 사용해 Python 스크립트를 생성하고 실행한다 (ooxml.md의 "Document Library" 섹션 참조)
4. 최종 문서 압축: `python ooxml/scripts/pack.py <input_directory> <office_file>`

Document 라이브러리는 일반적인 작업을 위한 고수준 메서드와 복잡한 시나리오를 위한 직접 DOM 접근을 모두 제공한다.

## 문서 검토를 위한 레드라인 워크플로우

이 워크플로우는 OOXML로 구현하기 전에 마크다운을 사용해 포괄적인 변경 추적을 계획할 수 있다. **중요**: 완전한 변경 추적을 위해서는 모든 변경사항을 체계적으로 구현해야 한다.

**배치 전략**: 관련 변경사항을 3~10개 단위로 묶는다. 이렇게 하면 디버깅이 용이해지면서 효율성도 유지된다. 다음 배치로 이동하기 전에 각 배치를 테스트한다.

**원칙: 최소한의 정밀한 편집**
변경 추적을 구현할 때는 실제로 변경되는 텍스트만 표시한다. 변경되지 않는 텍스트를 반복하면 편집 검토가 어려워지고 비전문적으로 보인다. 교체를 다음과 같이 분리한다: [변경 없는 텍스트] + [삭제] + [삽입] + [변경 없는 텍스트]. 원본 런의 RSID를 보존하기 위해 원본에서 `<w:r>` 요소를 추출해 재사용한다.

예시 - 문장에서 "30 days"를 "60 days"로 변경:
```python
# BAD - Replaces entire sentence
'<w:del><w:r><w:delText>The term is 30 days.</w:delText></w:r></w:del><w:ins><w:r><w:t>The term is 60 days.</w:t></w:r></w:ins>'

# GOOD - Only marks what changed, preserves original <w:r> for unchanged text
'<w:r w:rsidR="00AB12CD"><w:t>The term is </w:t></w:r><w:del><w:r><w:delText>30</w:delText></w:r></w:del><w:ins><w:r><w:t>60</w:t></w:r></w:ins><w:r w:rsidR="00AB12CD"><w:t> days.</w:t></w:r>'
```

### 변경 추적 워크플로우

1. **마크다운 표현 가져오기**: 변경 추적을 보존하며 문서를 마크다운으로 변환:
   ```bash
   pandoc --track-changes=all path-to-file.docx -o current.md
   ```

2. **변경사항 식별 및 그룹화**: 문서를 검토하고 필요한 모든 변경사항을 식별해 논리적 배치로 구성:

   **위치 방법** (XML에서 변경사항 찾기):
   - 섹션/제목 번호 (예: "Section 3.2", "Article IV")
   - 번호가 있는 경우 단락 식별자
   - 고유한 주변 텍스트가 있는 Grep 패턴
   - 문서 구조 (예: "첫 번째 단락", "서명 블록")
   - **마크다운 줄 번호 사용 금지** - XML 구조에 매핑되지 않는다

   **배치 구성** (배치당 3~10개의 관련 변경사항 묶기):
   - 섹션 기준: "배치 1: 섹션 2 수정", "배치 2: 섹션 5 업데이트"
   - 유형 기준: "배치 1: 날짜 수정", "배치 2: 당사자명 변경"
   - 복잡도 기준: 단순 텍스트 교체부터 시작해 복잡한 구조적 변경으로 진행
   - 순서 기준: "배치 1: 1-3페이지", "배치 2: 4-6페이지"

3. **문서 읽기 및 압축 해제**:
   - **필수 - 전체 파일 읽기**: [`ooxml.md`](ooxml.md)(약 600줄)를 처음부터 끝까지 완전히 읽는다. **이 파일을 읽을 때 절대 범위 제한을 설정하지 않는다.** "Document Library"와 "Tracked Change Patterns" 섹션에 특히 주의한다.
   - **문서 압축 해제**: `python ooxml/scripts/unpack.py <file.docx> <dir>`
   - **제안된 RSID 메모**: 압축 해제 스크립트가 변경 추적에 사용할 RSID를 제안한다. 4b단계에서 사용하기 위해 이 RSID를 복사한다.

4. **배치별 변경사항 구현**: 변경사항을 논리적으로 그룹화(섹션별, 유형별, 근접성 기준)하고 단일 스크립트에서 함께 구현한다. 이 방법의 장점:
   - 디버깅이 더 쉬워진다 (배치가 작을수록 오류 격리가 쉽다)
   - 점진적인 진행이 가능하다
   - 효율성 유지 (3~10개 변경사항 배치 크기가 적합하다)

   **제안된 배치 구성:**
   - 문서 섹션 기준 (예: "섹션 3 변경사항", "정의", "해지 조항")
   - 변경 유형 기준 (예: "날짜 변경", "당사자명 업데이트", "법적 용어 교체")
   - 근접성 기준 (예: "1-3페이지 변경사항", "문서 전반부 변경사항")

   관련 변경사항의 각 배치에 대해:

   **a. 텍스트를 XML에 매핑**: `word/document.xml`에서 텍스트를 Grep해 텍스트가 `<w:r>` 요소에 어떻게 분할되는지 확인한다.

   **b. 스크립트 생성 및 실행**: `get_node`로 노드를 찾고, 변경사항을 구현한 후 `doc.save()`를 실행한다. 패턴은 ooxml.md의 **"Document Library"** 섹션을 참조한다.

   **참고**: 스크립트 작성 전에 항상 `word/document.xml`을 즉시 Grep해 현재 줄 번호를 얻고 텍스트 내용을 확인한다. 줄 번호는 스크립트 실행마다 변경된다.

5. **문서 압축**: 모든 배치가 완료된 후, 압축 해제된 디렉터리를 .docx로 변환:
   ```bash
   python ooxml/scripts/pack.py unpacked reviewed-document.docx
   ```

6. **최종 검증**: 전체 문서를 종합적으로 확인:
   - 최종 문서를 마크다운으로 변환:
     ```bash
     pandoc --track-changes=all reviewed-document.docx -o verification.md
     ```
   - 모든 변경사항이 올바르게 적용됐는지 확인:
     ```bash
     grep "original phrase" verification.md  # Should NOT find it
     grep "replacement phrase" verification.md  # Should find it
     ```
   - 의도하지 않은 변경사항이 없는지 확인


## 문서를 이미지로 변환

Word 문서를 시각적으로 분석하려면 두 단계를 거쳐 이미지로 변환한다:

1. **DOCX를 PDF로 변환**:
   ```bash
   soffice --headless --convert-to pdf document.docx
   ```

2. **PDF 페이지를 JPEG 이미지로 변환**:
   ```bash
   pdftoppm -jpeg -r 150 document.pdf page
   ```
   이 명령은 `page-1.jpg`, `page-2.jpg` 등의 파일을 생성한다.

옵션:
- `-r 150`: 해상도를 150 DPI로 설정 (품질/크기 균형에 따라 조정)
- `-jpeg`: JPEG 형식으로 출력 (PNG를 원하면 `-png` 사용)
- `-f N`: 변환할 첫 페이지 (예: `-f 2`는 2페이지부터 시작)
- `-l N`: 변환할 마지막 페이지 (예: `-l 5`는 5페이지에서 종료)
- `page`: 출력 파일의 접두사

특정 범위 예시:
```bash
pdftoppm -jpeg -r 150 -f 2 -l 5 document.pdf page  # Converts only pages 2-5
```

## 코드 스타일 가이드라인
**중요**: DOCX 작업을 위한 코드 생성 시:
- 간결한 코드를 작성한다
- 장황한 변수명과 불필요한 연산을 피한다
- 불필요한 print 문을 피한다

## 의존성

필수 의존성 (설치되지 않은 경우 설치):

- **pandoc**: `sudo apt-get install pandoc` (텍스트 추출용)
- **docx**: `npm install -g docx` (새 문서 생성용)
- **LibreOffice**: `sudo apt-get install libreoffice` (PDF 변환용)
- **Poppler**: `sudo apt-get install poppler-utils` (PDF를 이미지로 변환하는 pdftoppm용)
- **defusedxml**: `pip install defusedxml` (안전한 XML 파싱용)
