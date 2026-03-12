---
name: document-office/xlsx
description: "Comprehensive spreadsheet creation, editing, and analysis with support for formulas, formatting, data analysis, and visualization. When Claude needs to work with spreadsheets (.xlsx, .xlsm, .csv, .tsv, etc) for: (1) Creating new spreadsheets with formulas and formatting, (2) Reading or analyzing data, (3) Modify existing spreadsheets while preserving formulas, (4) Data analysis and visualization in spreadsheets, or (5) Recalculating formulas"
license: Proprietary. LICENSE.txt has complete terms
---

# 출력물 요구 사항

## 모든 Excel 파일

### 수식 오류 제로
- 모든 Excel 모델은 수식 오류 (#REF!, #DIV/0!, #VALUE!, #N/A, #NAME?) 없이 납품되어야 한다

### 기존 템플릿 유지 (템플릿 업데이트 시)
- 파일 수정 시 기존 형식, 스타일, 관례를 연구하고 정확히 일치시키기
- 확립된 패턴이 있는 파일에 표준화된 서식 강요 금지
- 기존 템플릿 관례는 항상 이 가이드라인보다 우선

## 재무 모델

### 색상 코딩 표준
사용자나 기존 템플릿에서 별도로 명시하지 않는 경우

#### 업계 표준 색상 규칙
- **파란색 텍스트 (RGB: 0,0,255)**: 하드코딩된 입력값 및 사용자가 시나리오에 따라 변경할 숫자
- **검은색 텍스트 (RGB: 0,0,0)**: 모든 수식과 계산
- **초록색 텍스트 (RGB: 0,128,0)**: 동일 워크북 내 다른 워크시트에서 가져오는 링크
- **빨간색 텍스트 (RGB: 255,0,0)**: 다른 파일에 대한 외부 링크
- **노란색 배경 (RGB: 255,255,0)**: 주의가 필요한 핵심 가정 또는 업데이트가 필요한 셀

### 숫자 서식 표준

#### 필수 서식 규칙
- **연도**: 텍스트 문자열로 서식 지정 (예: "2024" - "2,024" 아님)
- **통화**: $#,##0 형식 사용; 헤더에 단위 항상 명시 ("Revenue ($mm)")
- **영(0)**: 숫자 서식으로 퍼센트 포함 모든 0을 "-"로 표시 (예: "$#,##0;($#,##0);-")
- **퍼센트**: 기본값 0.0% 형식 (소수점 한 자리)
- **배수**: 밸류에이션 배수 (EV/EBITDA, P/E)는 0.0x 형식
- **음수**: 마이너스 기호 -123 대신 괄호 (123) 사용

### 수식 작성 규칙

#### 가정값 배치
- 모든 가정값 (성장률, 마진, 배수 등)을 별도의 가정 셀에 배치
- 수식에서 하드코딩된 값 대신 셀 참조 사용
- 예시: =B5*1.05 대신 =B5*(1+$B$6) 사용

#### 수식 오류 방지
- 모든 셀 참조가 올바른지 확인
- 범위에서 off-by-one 오류 확인
- 모든 예측 기간에 걸쳐 일관된 수식 확보
- 엣지 케이스 테스트 (영값, 음수, 매우 큰 값)
- 의도하지 않은 순환 참조 없는지 확인

#### 하드코딩 값에 대한 문서화 요구 사항
- 셀 내 주석 또는 옆 셀에 기재 (표 끝인 경우). 형식: "Source: [시스템/문서], [날짜], [구체적 참조], [해당 시 URL]"
- 예시:
  - "Source: Company 10-K, FY2024, Page 45, Revenue Note, [SEC EDGAR URL]"
  - "Source: Company 10-Q, Q2 2025, Exhibit 99.1, [SEC EDGAR URL]"
  - "Source: Bloomberg Terminal, 8/15/2025, AAPL US Equity"
  - "Source: FactSet, 8/20/2025, Consensus Estimates Screen"

# XLSX 생성, 편집 및 분석

## 개요

사용자가 .xlsx 파일의 생성, 편집 또는 내용 분석을 요청할 수 있다. 작업 종류에 따라 다양한 도구와 워크플로우를 사용할 수 있다.

## 중요 요구 사항

**수식 재계산에 LibreOffice 필요**: `recalc.py` 스크립트를 사용하여 수식 값을 재계산하기 위해 LibreOffice가 설치되어 있다고 가정한다. 스크립트는 첫 실행 시 LibreOffice를 자동으로 구성한다

## 데이터 읽기 및 분석

### pandas를 사용한 데이터 분석
데이터 분석, 시각화, 기본 작업에는 강력한 데이터 조작 기능을 제공하는 **pandas**를 사용한다:

```python
import pandas as pd

# Excel 읽기
df = pd.read_excel('file.xlsx')  # Default: first sheet
all_sheets = pd.read_excel('file.xlsx', sheet_name=None)  # All sheets as dict

# 분석
df.head()      # 데이터 미리보기
df.info()      # 열 정보
df.describe()  # 통계

# Excel 쓰기
df.to_excel('output.xlsx', index=False)
```

## Excel 파일 워크플로우

## 중요: 하드코딩 값 대신 수식 사용

**Python에서 값을 계산하여 하드코딩하는 대신 항상 Excel 수식을 사용한다.** 이렇게 하면 스프레드시트가 동적으로 업데이트 가능한 상태를 유지한다.

### ❌ 잘못된 방법 - 계산된 값 하드코딩
```python
# 잘못됨: Python에서 계산하고 결과를 하드코딩
total = df['Sales'].sum()
sheet['B10'] = total  # Hardcodes 5000

# 잘못됨: Python에서 성장률 계산
growth = (df.iloc[-1]['Revenue'] - df.iloc[0]['Revenue']) / df.iloc[0]['Revenue']
sheet['C5'] = growth  # Hardcodes 0.15

# 잘못됨: 평균의 Python 계산
avg = sum(values) / len(values)
sheet['D20'] = avg  # Hardcodes 42.5
```

### ✅ 올바른 방법 - Excel 수식 사용
```python
# 좋음: Excel이 합계를 계산하도록
sheet['B10'] = '=SUM(B2:B9)'

# 좋음: Excel 수식으로 성장률
sheet['C5'] = '=(C4-C2)/C2'

# 좋음: Excel 함수로 평균
sheet['D20'] = '=AVERAGE(D2:D19)'
```

이는 합계, 퍼센트, 비율, 차이 등 모든 계산에 적용된다. 소스 데이터 변경 시 스프레드시트가 재계산될 수 있어야 한다.

## 일반 워크플로우
1. **도구 선택**: 데이터용 pandas, 수식/서식용 openpyxl
2. **생성/로드**: 새 워크북 생성 또는 기존 파일 로드
3. **수정**: 데이터, 수식, 서식 추가/편집
4. **저장**: 파일에 쓰기
5. **수식 재계산 (수식 사용 시 필수)**: recalc.py 스크립트 사용
   ```bash
   python recalc.py output.xlsx
   ```
6. **오류 확인 및 수정**:
   - 스크립트가 오류 상세 정보가 담긴 JSON 반환
   - `status`가 `errors_found`이면 `error_summary`에서 특정 오류 유형과 위치 확인
   - 식별된 오류 수정 후 재계산
   - 수정할 일반 오류:
     - `#REF!`: 잘못된 셀 참조
     - `#DIV/0!`: 0으로 나누기
     - `#VALUE!`: 수식에 잘못된 데이터 유형
     - `#NAME?`: 인식할 수 없는 수식명

### 새 Excel 파일 생성

```python
# 수식 및 서식에 openpyxl 사용
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment

wb = Workbook()
sheet = wb.active

# 데이터 추가
sheet['A1'] = 'Hello'
sheet['B1'] = 'World'
sheet.append(['Row', 'of', 'data'])

# 수식 추가
sheet['B2'] = '=SUM(A1:A10)'

# 서식
sheet['A1'].font = Font(bold=True, color='FF0000')
sheet['A1'].fill = PatternFill('solid', start_color='FFFF00')
sheet['A1'].alignment = Alignment(horizontal='center')

# 열 너비
sheet.column_dimensions['A'].width = 20

wb.save('output.xlsx')
```

### 기존 Excel 파일 편집

```python
# 수식과 서식을 유지하기 위해 openpyxl 사용
from openpyxl import load_workbook

# 기존 파일 로드
wb = load_workbook('existing.xlsx')
sheet = wb.active  # or wb['SheetName'] for specific sheet

# 여러 시트 작업
for sheet_name in wb.sheetnames:
    sheet = wb[sheet_name]
    print(f"Sheet: {sheet_name}")

# 셀 수정
sheet['A1'] = 'New Value'
sheet.insert_rows(2)  # 2번 위치에 행 삽입
sheet.delete_cols(3)  # 3번 열 삭제

# 새 시트 추가
new_sheet = wb.create_sheet('NewSheet')
new_sheet['A1'] = 'Data'

wb.save('modified.xlsx')
```

## 수식 재계산

openpyxl로 생성하거나 수정한 Excel 파일에는 수식이 문자열로 포함되지만 계산된 값은 없다. 제공된 `recalc.py` 스크립트를 사용하여 수식을 재계산한다:

```bash
python recalc.py <excel_file> [timeout_seconds]
```

예시:
```bash
python recalc.py output.xlsx 30
```

스크립트 동작:
- 첫 실행 시 LibreOffice 매크로 자동 설정
- 모든 시트의 모든 수식 재계산
- 모든 셀에서 Excel 오류 (#REF!, #DIV/0! 등) 스캔
- 상세한 오류 위치와 수를 포함한 JSON 반환
- Linux와 macOS 모두 지원

## 수식 검증 체크리스트

수식이 올바르게 작동하는지 확인하기 위한 빠른 점검:

### 필수 검증
- [ ] **샘플 참조 2~3개 테스트**: 전체 모델 구축 전에 올바른 값을 가져오는지 확인
- [ ] **열 매핑**: Excel 열이 일치하는지 확인 (예: 열 64 = BL, BK 아님)
- [ ] **행 오프셋**: Excel 행은 1부터 인덱스 (DataFrame 행 5 = Excel 행 6)

### 일반적인 함정
- [ ] **NaN 처리**: `pd.notna()`로 null 값 확인
- [ ] **오른쪽 끝 열**: FY 데이터가 50번 이상의 열에 있는 경우 많음
- [ ] **여러 일치**: 첫 번째만이 아닌 모든 경우 검색
- [ ] **0으로 나누기**: 수식에서 `/` 사용 전 분모 확인 (#DIV/0!)
- [ ] **잘못된 참조**: 모든 셀 참조가 의도한 셀을 가리키는지 확인 (#REF!)
- [ ] **시트 간 참조**: 시트 연결에 올바른 형식 사용 (Sheet1!A1)

### 수식 테스트 전략
- [ ] **작게 시작**: 광범위하게 적용하기 전에 2~3개 셀에서 수식 테스트
- [ ] **의존성 확인**: 수식에서 참조하는 모든 셀이 존재하는지 확인
- [ ] **엣지 케이스 테스트**: 영, 음수, 매우 큰 값 포함

### recalc.py 출력 해석
스크립트가 오류 상세 정보가 담긴 JSON 반환:
```json
{
  "status": "success",           // or "errors_found"
  "total_errors": 0,              // 총 오류 수
  "total_formulas": 42,           // 파일의 수식 수
  "error_summary": {              // 오류 발견 시에만 존재
    "#REF!": {
      "count": 2,
      "locations": ["Sheet1!B5", "Sheet1!C10"]
    }
  }
}
```

## 모범 사례

### 라이브러리 선택
- **pandas**: 데이터 분석, 대량 작업, 간단한 데이터 내보내기에 최적
- **openpyxl**: 복잡한 서식, 수식, Excel 특화 기능에 최적

### openpyxl 사용 시
- 셀 인덱스는 1부터 시작 (row=1, column=1은 셀 A1 참조)
- 계산된 값 읽기에 `data_only=True` 사용: `load_workbook('file.xlsx', data_only=True)`
- **경고**: `data_only=True`로 열고 저장하면 수식이 값으로 대체되어 영구 손실
- 대용량 파일: 읽기에 `read_only=True`, 쓰기에 `write_only=True` 사용
- 수식은 유지되지만 평가되지 않음 - 값 업데이트에 recalc.py 사용

### pandas 사용 시
- 추론 문제 방지를 위해 데이터 유형 지정: `pd.read_excel('file.xlsx', dtype={'id': str})`
- 대용량 파일은 특정 열만 읽기: `pd.read_excel('file.xlsx', usecols=['A', 'C', 'E'])`
- 날짜 올바르게 처리: `pd.read_excel('file.xlsx', parse_dates=['date_column'])`

## 코드 스타일 가이드라인
**중요**: Excel 작업을 위한 Python 코드 생성 시:
- 불필요한 주석 없이 최소한의 간결한 Python 코드 작성
- 장황한 변수명과 불필요한 연산 피하기
- 불필요한 print 문 피하기

**Excel 파일 자체의 경우**:
- 복잡한 수식이나 중요한 가정이 있는 셀에 주석 추가
- 하드코딩된 값의 데이터 소스 문서화
- 핵심 계산 및 모델 섹션에 대한 메모 포함
